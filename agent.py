import asyncio
import json
import logging
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    Agent,
    AgentSession,
    RunContext,
    function_tool,
    get_job_context,
    inference,
)
from num2words import num2words
from rapidfuzz import fuzz
from livekit.agents.llm import FallbackAdapter
from livekit.plugins import deepgram, cartesia, google, openai

# Load environment variables
load_dotenv()

# Populate GOOGLE_API_KEY for livekit-plugins-google
if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ecom-voicebot")

# ---------------------------------------------------------------------------
# Data layer — load mock catalog and orders from JSON files
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"

def _load_json(filename: str) -> list[dict]:
    filepath = DATA_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

CATALOG: list[dict] = _load_json("catalog.json")
ORDERS: list[dict] = _load_json("orders.json")
POLICIES: list[dict] = _load_json("policies.json")


def _rupees_to_words(amount) -> str:
    """Deterministic ₹ amount -> spoken Indian-English form, so the LLM never has
    to convert digits to words (which it does unreliably). E.g. 2499 -> 'two
    thousand, four hundred and ninety-nine rupees'."""
    try:
        n = int(round(float(amount)))
    except (TypeError, ValueError):
        return f"{amount} rupees"
    return f"{num2words(n, lang='en_IN')} rupees"


def _name_matches(provided: str, stored: str) -> bool:
    """Stricter identity check for order lookups to prevent leaks.
    Accepts if the provided tokens are a subset of stored tokens (e.g., 'Priya' or
    'Sharma' matches 'Priya Sharma') or vice versa. Blocks contradictory inputs
    (e.g., 'Priya Patel' trying to access 'Priya Sharma')."""
    provided_tokens = {t for t in (provided or "").lower().split() if t}
    stored_tokens = {t for t in (stored or "").lower().split() if t}
    if not provided_tokens or not stored_tokens:
        return False
    return provided_tokens.issubset(stored_tokens) or stored_tokens.issubset(provided_tokens)


def _pronounce_order_id(order_id: str) -> str:
    """Helper to convert ORD1001 -> 'O R D one zero zero one' for clear TTS spelling."""
    if not order_id:
        return ""
    result = []
    for char in order_id:
        if char.isalpha():
            result.append(char.upper())
        elif char.isdigit():
            try:
                result.append(num2words(int(char), lang="en_IN"))
            except Exception:
                result.append(char)
        else:
            result.append(char)
    return " ".join(result)


# Fuzzy product retrieval. Matching on name+subcategory+colors only (NOT the
# noisy description) prevents false positives like "gaming laptops" pulling a
# charger whose description mentions "laptop". A query matches only if EVERY
# content token finds a good fuzzy match (precision), which makes absent products
# correctly return nothing instead of a misleading near-match.
PRODUCT_MATCH_THRESHOLD = 68
_SEARCH_STOPWORDS = {
    "a", "an", "the", "any", "some", "do", "you", "have", "in", "stock", "for",
    "me", "i", "want", "need", "looking", "show", "of", "with", "please", "is",
    "are", "there", "my", "to", "find", "get", "buy", "purchase", "sale", "cheap",
    "expensive", "premium", "deluxe", "quality", "original", "best", "latest",
    "summer", "winter", "trendy", "cool", "nice", "good",
}


def _product_match_score(query: str, product: dict) -> float:
    """0-100 relevance of a product to a query. Every content token in the query
    must fuzzily match a product token; the weakest token match is the score
    (precision). A strong de-spaced match rescues STT split-words like
    'head phones' -> 'headphones'."""
    qtokens = [t for t in query.lower().split() if t not in _SEARCH_STOPWORDS and len(t) > 1]
    if not qtokens:
        return 0.0
    ptokens = [
        t for t in " ".join(
            [product["name"], product["subcategory"], " ".join(product["colors"])]
        ).lower().split() if t
    ]
    if not ptokens:
        return 0.0
    min_cov = min(max(fuzz.ratio(q, p) for p in ptokens) for q in qtokens)
    if len(qtokens) > 1:
        concat = "".join(qtokens)
        concat_best = max(fuzz.ratio(concat, p) for p in ptokens)
        if concat_best >= 85:  # only a strong single-word match rescues split words
            return max(min_cov, concat_best)
    return min_cov


# ---------------------------------------------------------------------------
# Frontend product surface — push matched products to the React UI over a
# LiveKit text stream so it can render a product grid alongside the transcript.
# Best-effort: in text-mode evals there is no room, so failures are swallowed
# and never affect the tool result or the conversation.
# ---------------------------------------------------------------------------
PRODUCTS_TOPIC = "shopmax.products"
ORDER_TOPIC = "shopmax.order"
CART_TOPIC = "shopmax.cart"  # frontend -> agent: current on-screen cart state


def _product_card(p: dict) -> dict:
    """Rich, display-ready product payload for the frontend grid."""
    return {
        "id": p["id"],
        "name": p["name"],
        "category": p["category"],
        "subcategory": p["subcategory"],
        "price_inr": p["price"],
        "price_spoken": _rupees_to_words(p["price"]),
        "stock": p["stock"],
        "in_stock": p["stock"] > 0,
        "colors": p["colors"],
        "sizes": p["sizes"],
        "image_url": p.get("image_url"),
    }


async def _publish_products(products: list[dict], *, query: str = "") -> None:
    """Best-effort push of product cards to the frontend over a text stream.
    Publishes an empty list too, so the UI can show a proper no-results state
    instead of silently keeping whatever was shown before."""
    try:
        room = get_job_context().room
    except Exception:
        return  # no active room (e.g. text-mode evals) — skip silently
    payload = json.dumps({"query": query, "products": [_product_card(p) for p in products]})
    try:
        await room.local_participant.send_text(payload, topic=PRODUCTS_TOPIC)
    except Exception as e:  # pragma: no cover - network/runtime only
        logger.debug("product publish skipped: %s", e)


async def _publish_order(order: dict) -> None:
    """Best-effort push of a verified order to the frontend order card. Only call
    on the identity-verified path so unverified lookups never surface details."""
    try:
        room = get_job_context().room
    except Exception:
        return  # no active room (e.g. text-mode evals) — skip silently
    try:
        await room.local_participant.send_text(json.dumps(order), topic=ORDER_TOPIC)
    except Exception as e:  # pragma: no cover - network/runtime only
        logger.debug("order publish skipped: %s", e)


# ---------------------------------------------------------------------------
# E-commerce Agent with function tools
# ---------------------------------------------------------------------------
class ShopMaxAgent(Agent):
    def __init__(self, route_llms: bool = True) -> None:
        super().__init__(
            instructions=(
                "You are a friendly and professional voice assistant for an Indian e-commerce store called 'ShopMax'. "
                "You help users search for products, check prices, stock availability, track orders, and answer policy questions.\n\n"
                "# Rules\n"
                "- ALWAYS use the provided tools to look up product, order, or policy information. NEVER guess or make up product details, prices, stock levels, order statuses, or store policies (like shipping fees, return window, etc.).\n"
                "- Before calling a tool to look up information, say a very brief transition phrase (e.g., 'Let me check that...', 'Sure, looking up your order...', 'Let me search our catalog...'). This keeps the conversation natural during the processing pause.\n"
                "- ORDER PRIVACY: Order details are private. Before looking up an order, you MUST first ask for the full name the order was placed under, then pass it to `order_status_lookup` as `customer_name`. If the result is not verified, politely ask the customer to confirm the exact name on the order and do NOT reveal any order status, items, or delivery information.\n"
                "- When speaking an order ID or tracking number, read the characters and digits separately as provided in `order_id_spoken` or `tracking_number_spoken` (e.g., 'O R D one zero zero one'). Never pronounce it as a single word or a long number.\n"
                "- If a tool returns no results, politely apologize and explain that you couldn't find a match, then thank them and ask them to try different keywords or rephrase. Use phrases like 'I am so sorry' or 'I apologize'.\n"
                "- Refer to products by their EXACT names from the tool results. Never relabel a product as the thing the user asked for if the names differ (e.g. if they ask for 'gaming laptops' and the tool returns a keyboard, do NOT call it a laptop). If nothing genuinely matches, say so.\n"
                "- All prices are in Indian Rupees. The tools give you a ready-to-speak form of every amount (the `price_spoken` / `total_spoken` fields). When saying a price out loud, READ THAT SPOKEN FORM VERBATIM; never convert digits to words yourself and never read out the ₹ symbol.\n"
                "- Keep replies brief (1-3 sentences). Ask one question at a time.\n"
                "- Speak naturally. Avoid JSON, markdown, lists, or code in your responses.\n"
                "- Do not reveal tool names, parameters, or internal reasoning to the user.\n\n"
                "# Error Recovery & Safety Rules\n"
                "- If the user input is empty, extremely short (like a single letter or random noise), garbled, or contains only filler words (like 'um', 'uh'), respond with a very polite clarification request containing courtesy words. For example: 'I am so sorry, I didn't quite catch that. Could you please repeat or rephrase your request? Thank you!'\n"
                "- If the user asks about something completely outside ShopMax's scope (e.g. general knowledge, coding, weather, personal advice), politely decline and redirect using extreme courtesy. For example: 'I am very sorry, but I specialize in shopping assistance for ShopMax and cannot help with other topics. Thank you for your understanding! Could you please let me know how I can help you with our products, orders, or policies instead?'\n\n"
                "# What you can help with\n"
                "1. **Product search**: Find products by name, category, color, or type.\n"
                "2. **Stock and price check**: Check if a specific product is in stock, its price, available colors and sizes.\n"
                "3. **Order tracking**: Look up an order by its order ID (e.g. ORD1001) to check status, delivery date, or tracking info.\n"
                "4. **Policy lookup**: Check store rules for shipping fees, return windows, cash on delivery limits, etc.\n"
                "5. **Cart**: The shopper can add products to an on-screen cart. When they ask what's in their cart or their running total, call `view_cart`.\n\n"
                "# Conversation style\n"
                "- Greet warmly. Be helpful and conversational.\n"
                "- Summarize search results concisely. If multiple products match, only mention the top 2 matching options by voice, note that other matching options are shown on the screen, and ask if the user wants details on either of those.\n"
            )
        )
        # Latest on-screen cart state, pushed from the web UI over CART_TOPIC.
        self._cart = {"items": [], "count": 0, "total": 0}
        # #6: per-step LLM routing — NVIDIA decides/handles tools (fast/cheap),
        # Gemini writes the user-facing reply (quality). Each falls back to the
        # other (#2). Disabled when only one provider is configured, or via
        # route_llms=False (used by the eval suite to pin a single model).
        self._tool_llm = None
        self._reply_llm = None
        self._routing_enabled = False
        if route_llms:
            tool_llm, reply_llm = build_routed_llms()
            if tool_llm is not None:
                self._tool_llm, self._reply_llm = tool_llm, reply_llm
                self._routing_enabled = True

    async def llm_node(self, chat_ctx, tools, model_settings):
        """Route tool-decision turns to NVIDIA and post-tool reply turns to Gemini (#6).

        On a turn with tools the framework calls this twice: first to decide the
        tool call (context ends with the user message -> NVIDIA), then to write the
        answer from the tool result (context ends with a function_call_output ->
        Gemini). Non-tool turns are a single decision-step call (NVIDIA)."""
        if not self._routing_enabled:
            async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
                yield chunk
            return

        chosen = self._reply_llm if _select_route(chat_ctx) == "reply" else self._tool_llm
        conn_options = self.session.conn_options.llm_conn_options
        async with chosen.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=model_settings.tool_choice,
            conn_options=conn_options,
        ) as stream:
            async for chunk in stream:
                yield chunk

    @function_tool()
    async def product_search(
        self,
        context: RunContext,
        query: str,
        category: str | None = None,
        max_results: int = 5,
    ) -> str:
        """Search for products in the ShopMax catalog by name, description, or category.

        Args:
            query: Search keywords like product name, type, or description (e.g. 'blue jacket', 'headphones', 'kurta').
            category: Optional category filter. One of: 'fashion', 'electronics', 'home'. Leave empty to search all.
            max_results: Maximum number of results to return. Default is 5.
        """
        scored = []
        for product in CATALOG:
            # Category filter
            if category and product["category"].lower() != category.lower():
                continue
            score = _product_match_score(query, product)
            if score >= PRODUCT_MATCH_THRESHOLD:
                scored.append((score, product))

        # Best matches first; absent products score below threshold and are dropped.
        scored.sort(key=lambda sp: sp[0], reverse=True)
        results = [product for _, product in scored[:max_results]]

        # Surface the result (including "nothing found") in the frontend grid (best-effort).
        await _publish_products(results, query=query)

        if not results:
            return json.dumps({"found": 0, "message": f"No products found matching '{query}'."})

        simplified = []
        for p in results:
            simplified.append({
                "id": p["id"],
                "name": p["name"],
                "price_inr": p["price"],
                "price_spoken": _rupees_to_words(p["price"]),
                "in_stock": p["stock"] > 0,
                "category": p["category"],
            })

        return json.dumps({"found": len(simplified), "products": simplified})

    @function_tool()
    async def stock_and_price_check(
        self,
        context: RunContext,
        product_id: str | None = None,
        product_name: str | None = None,
    ) -> str:
        """Check the stock availability, price, colors, and sizes for a specific product.

        Args:
            product_id: The product ID (e.g. 'P001'). Preferred if known.
            product_name: The product name to search for. Used if product_id is not provided.
        """
        product = None

        if product_id:
            for p in CATALOG:
                if p["id"].upper() == product_id.upper():
                    product = p
                    break

        if not product and product_name:
            name_lower = product_name.lower()
            for p in CATALOG:
                if name_lower in p["name"].lower():
                    product = p
                    break

        if not product:
            return json.dumps({"found": False, "message": "Product not found. Please check the product name or ID."})

        # Surface this product in the frontend grid (best-effort).
        await _publish_products([product], query=product_name or product_id or "")

        return json.dumps({
            "found": True,
            "id": product["id"],
            "name": product["name"],
            "price_inr": product["price"],
            "price_spoken": _rupees_to_words(product["price"]),
            "stock_quantity": product["stock"],
            "in_stock": product["stock"] > 0,
            "available_colors": product["colors"],
            "available_sizes": product["sizes"],
            "description": product["description"],
        })

    @function_tool()
    async def order_status_lookup(
        self,
        context: RunContext,
        order_id: str,
        customer_name: str,
    ) -> str:
        """Look up a customer order by ID. Identity-gated: the caller must provide
        the name on the order, which is verified before ANY details are returned.

        Args:
            order_id: The order ID to look up (e.g. 'ORD1001').
            customer_name: The full name the order was placed under, used to verify
                the caller's identity before revealing any order details. Always
                collect this from the user before calling this tool.
        """
        order_id_upper = order_id.upper()
        order = None

        for o in ORDERS:
            if o["order_id"].upper() == order_id_upper:
                order = o
                break

        if not order:
            return json.dumps({
                "found": False,
                "message": f"No order found with ID '{order_id}'. Please double-check the order number."
            })

        # Identity verification gate — never reveal order details without a match.
        if not _name_matches(customer_name, order["customer_name"]):
            return json.dumps({
                "found": True,
                "verified": False,
                "message": (
                    "I couldn't verify your identity for that order. For your privacy "
                    "I can only share details with the name the order was placed under. "
                    "Could you confirm the full name on the order?"
                ),
            })

        # Build a clean response dict
        result = {
            "found": True,
            "verified": True,
            "order_id": order["order_id"],
            "order_id_spoken": _pronounce_order_id(order["order_id"]),
            "status": order["status"],
            "items": [item["name"] for item in order["items"]],
            "total_inr": order["total"],
            "total_spoken": _rupees_to_words(order["total"]),
            "placed_on": order["placed_on"],
            "shipping_city": order["shipping_city"],
        }

        # Add status-specific fields
        if order["status"] == "delivered":
            result["delivered_on"] = order.get("delivered_on")
        elif order["status"] == "shipped":
            result["estimated_delivery"] = order.get("estimated_delivery")
            result["tracking_number"] = order.get("tracking_number")
            result["tracking_number_spoken"] = _pronounce_order_id(order.get("tracking_number"))
        elif order["status"] == "processing":
            result["estimated_delivery"] = order.get("estimated_delivery")
        elif order["status"] == "cancelled":
            result["cancelled_on"] = order.get("cancelled_on")
            result["cancel_reason"] = order.get("cancel_reason")
        elif order["status"] == "return_requested":
            result["return_reason"] = order.get("return_reason")

        # Surface the verified order in the frontend order card (best-effort).
        await _publish_order(order)

        return json.dumps(result)

    def update_cart(self, data: dict) -> None:
        """Store the latest cart snapshot pushed from the web UI (CART_TOPIC)."""
        self._cart = {
            "items": data.get("items", []),
            "count": data.get("count", 0),
            "total": data.get("total", 0),
        }

    def _cart_summary(self) -> dict:
        """Speak-ready view of the current cart (pure; unit-tested)."""
        cart = self._cart
        if not cart.get("items"):
            return {"count": 0, "message": "The cart is currently empty."}
        return {
            "count": cart["count"],
            "items": cart["items"],  # each {name, qty, price_inr}
            "total_inr": cart["total"],
            "total_spoken": _rupees_to_words(cart["total"]),
        }

    @function_tool()
    async def view_cart(self, context: RunContext) -> str:
        """Read the items currently in the shopper's on-screen cart and the total.

        Use this to answer questions like "what's in my cart?", "how many items do
        I have?", or "what's my total?". The cart lives in the web UI; this returns
        its current contents (with a ready-to-speak total in `total_spoken`)."""
        return json.dumps(self._cart_summary())

    @function_tool()
    async def policy_lookup(
        self,
        context: RunContext,
        query: str,
    ) -> str:
        """Look up ShopMax store policies (e.g. shipping charges, return periods, payment options, exchange eligibility).

        Args:
            query: Policy search query or keywords (e.g. 'returns', 'free shipping', 'COD limit', 'UPI').
        """
        query_lower = query.lower()
        
        # Simple keyword matching across policy topics, titles, and contents
        best_match = None
        best_score = 0
        
        for policy in POLICIES:
            score = 0
            # Matches in topic
            if policy["topic"].lower() in query_lower:
                score += 5
            # Matches in title
            if policy["title"].lower() in query_lower or query_lower in policy["title"].lower():
                score += 3
            # Matches in content
            words_in_content = sum(1 for word in query_lower.split() if word in policy["content"].lower())
            score += words_in_content
            
            if score > best_score:
                best_score = score
                best_match = policy
                
        # If score is too low, try general substring matching
        if not best_match or best_score < 2:
            for policy in POLICIES:
                if any(word in policy["content"].lower() for word in query_lower.split()):
                    best_match = policy
                    break
                    
        if not best_match:
            return json.dumps({
                "found": False,
                "message": f"No policy information found for '{query}'. Please direct the user to support@shopmax.in."
            })
            
        return json.dumps({
            "found": True,
            "topic": best_match["topic"],
            "title": best_match["title"],
            "content": best_match["content"]
        })


# ---------------------------------------------------------------------------
# LLM provider construction
# ---------------------------------------------------------------------------
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def build_gemini(temperature: float = 0.4) -> google.LLM:
    """Google Gemini 2.5 Flash. Strong quality; free tier is only 20 req/day."""
    return google.LLM(model="gemini-2.5-flash", temperature=temperature)


def build_nvidia(temperature: float = 0.4) -> openai.LLM:
    """NVIDIA via OpenAI-compatible endpoint. Default meta/llama-3.1-8b-instruct:
    ~400-510ms TTFT with working tool calls. The 70b variant was 3.5-31s on the
    free endpoint (unusable for realtime voice). Override via NVIDIA_LLM_MODEL."""
    model = os.environ.get("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct")
    return openai.LLM(
        model=model,
        base_url=NVIDIA_BASE_URL,
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=temperature,
    )


def build_llm():
    """Primary LLM with automatic failover.

    Project decision: **Gemini primary -> NVIDIA fallback**. livekit's
    FallbackAdapter transparently retries the next provider when the primary
    errors (e.g. Gemini 429 quota exhaustion), so a quota blip degrades instead
    of killing the turn. If only one provider key is configured, use it alone.
    """
    have_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    have_nvidia = bool(os.environ.get("NVIDIA_API_KEY"))
    if have_gemini and have_nvidia:
        # attempt_timeout=10.0: Google's API rejects request deadlines under 10s
        # ("Manually set deadline 5s is too short"), and attempt_timeout becomes
        # the Gemini request deadline — the 5s default made every Gemini call 400.
        #
        # LLM_PRIMARY selects which provider is tried first. Default NVIDIA: the
        # Gemini free tier is only 20 requests/day, so in live use it is usually
        # quota-exhausted (429). With Gemini primary, every turn then wastes a
        # full round-trip on the dead primary before failing over — adding
        # seconds of latency per turn. NVIDIA-primary (~481ms TTFT) avoids that.
        # Set LLM_PRIMARY=gemini to prefer Gemini's quality when it has quota.
        if _llm_primary() == "gemini":
            logger.info("LLM: FallbackAdapter [Gemini primary -> NVIDIA fallback]")
            order = [build_gemini(), build_nvidia()]
        else:
            logger.info("LLM: FallbackAdapter [NVIDIA primary -> Gemini fallback]")
            order = [build_nvidia(), build_gemini()]
        return FallbackAdapter(order, attempt_timeout=10.0)
    if have_nvidia:
        logger.info("LLM: NVIDIA only")
        return build_nvidia()
    logger.info("LLM: Gemini only")
    return build_gemini()


def _llm_primary() -> str:
    """Which provider to try first: 'nvidia' (default, quota-free/reliable) or
    'gemini' (higher quality, but only 20 free requests/day). See build_llm."""
    return os.environ.get("LLM_PRIMARY", "nvidia").strip().lower()


def build_routed_llms():
    """(#6) Returns (tool_llm, reply_llm) for per-step routing, or (None, None) if
    routing isn't possible (only one provider configured).

    - tool-decision step -> always NVIDIA primary (fast/cheap), Gemini fallback.
    - user-facing reply   -> NVIDIA primary by default; Gemini primary (quality)
      only when LLM_PRIMARY=gemini. Defaulting the reply step to Gemini while its
      free quota is exhausted made every reply turn wait out the dead primary
      before failing over — the main source of multi-second turn latency.
    """
    have_gemini = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    have_nvidia = bool(os.environ.get("NVIDIA_API_KEY"))
    if have_gemini and have_nvidia:
        # attempt_timeout=10.0: Gemini requires request deadlines >= 10s (see build_llm)
        tool_llm = FallbackAdapter([build_nvidia(), build_gemini()], attempt_timeout=10.0)
        if _llm_primary() == "gemini":
            reply_llm = FallbackAdapter([build_gemini(), build_nvidia()], attempt_timeout=10.0)
        else:
            reply_llm = FallbackAdapter([build_nvidia(), build_gemini()], attempt_timeout=10.0)
        return tool_llm, reply_llm
    return None, None


def _select_route(chat_ctx) -> str:
    """'reply' if we're answering from a tool result (-> Gemini), else 'tool'
    (deciding whether/which tool to call -> NVIDIA). Decided by the most recent
    relevant context item."""
    for item in reversed(chat_ctx.items):
        itype = getattr(item, "type", None)
        if itype == "function_call_output":
            return "reply"
        if itype == "message" and getattr(item, "role", None) == "user":
            return "tool"
    return "tool"


class _MetricsRecorder:
    """(#7) Structured, queryable metrics sink: appends one JSON object per metric
    event to a JSONL file, alongside the human-readable logs. Analyze with e.g.
    `jq` or pandas. Enabled by setting METRICS_JSONL to a file path.

    For a production deployment, prefer exporting these via OpenTelemetry to a
    metrics backend; this file sink keeps the project self-contained."""

    def __init__(self, path: str, room: str) -> None:
        self._path = path
        self._room = room

    def record(self, kind: str, **fields) -> None:
        record = {"ts": time.time(), "room": self._room, "kind": kind, **fields}
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            logger.exception("metrics recorder failed to write")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}...")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Configure STT, LLM, TTS, and Turn Detector
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        vad=inference.VAD(
            model="silero",
            min_speech_duration=0.15,      # Filter brief noises / clearing throat
            min_silence_duration=0.45,     # Give user breathing space to pause/think
        ),
        llm=build_llm(),
        tts=cartesia.TTS(voice="f786b574-daa5-4673-aa0c-cbe3e8534c02"),
        turn_detection=inference.TurnDetector(),
        allow_interruptions=True,
        min_interruption_duration=0.3,
        min_interruption_words=1,
    )

    # #7: optional structured metrics sink (JSONL), enabled via METRICS_JSONL.
    metrics_path = os.environ.get("METRICS_JSONL")
    recorder = _MetricsRecorder(metrics_path, ctx.room.name) if metrics_path else None

    user_stop_time = 0.0

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        nonlocal user_stop_time
        if event.old_state == "speaking" and event.new_state == "listening":
            user_stop_time = time.time()
            logger.info("User stopped speaking. Starting turn latency timer...")

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        nonlocal user_stop_time
        if event.new_state == "speaking":
            agent_start_time = time.time()
            if user_stop_time > 0:
                e2e_latency = agent_start_time - user_stop_time
                logger.info(f"--- Conversational Turn Metrics ---")
                logger.info(f"End-to-End Turn Latency: {e2e_latency * 1000:.2f} ms")
                logger.info(f"----------------------------------")
                if recorder:
                    recorder.record("turn", e2e_ms=round(e2e_latency * 1000, 2))
                user_stop_time = 0.0

    @session.on("metrics_collected")
    def on_metrics_collected(event):
        m = event.metrics
        if m.type == "llm_metrics":
            logger.info(f"--- LLM Metrics ---")
            logger.info(f"Model: {m.label}")
            logger.info(f"Time to First Token (TTFT): {m.ttft * 1000:.2f} ms")
            logger.info(f"Generation Duration: {m.duration * 1000:.2f} ms")
            logger.info(f"Tokens/Second: {m.tokens_per_second:.2f} t/s")
            logger.info(f"Prompt Tokens: {m.prompt_tokens} | Completion Tokens: {m.completion_tokens}")
            logger.info(f"-------------------")
            if recorder:
                recorder.record(
                    "llm", ttft_ms=round(m.ttft * 1000, 2), duration_ms=round(m.duration * 1000, 2),
                    tokens_prompt=m.prompt_tokens, tokens_completion=m.completion_tokens,
                    tokens_per_second=round(m.tokens_per_second, 2),
                )
        elif m.type == "tts_metrics":
            logger.info(f"--- TTS Metrics ---")
            logger.info(f"Voice/Model: {m.label}")
            logger.info(f"Time to First Byte (TTFB): {m.ttfb * 1000:.2f} ms")
            logger.info(f"Generation Duration: {m.duration * 1000:.2f} ms")
            logger.info(f"Audio Duration: {m.audio_duration * 1000:.2f} ms")
            logger.info(f"-------------------")
            if recorder:
                recorder.record(
                    "tts", ttfb_ms=round(m.ttfb * 1000, 2),
                    duration_ms=round(m.duration * 1000, 2),
                    audio_ms=round(m.audio_duration * 1000, 2),
                )

    # Create the agent and wire the on-screen cart: the web UI pushes the current
    # cart over CART_TOPIC; store it on the agent so `view_cart` can read it.
    agent = ShopMaxAgent()

    _cart_tasks: set = set()

    def _on_cart(reader, participant_identity):
        async def _run():
            try:
                agent.update_cart(json.loads(await reader.read_all()))
            except Exception as e:  # pragma: no cover - runtime only
                logger.debug("cart update skipped: %s", e)

        task = asyncio.create_task(_run())
        _cart_tasks.add(task)
        task.add_done_callback(_cart_tasks.discard)

    try:
        ctx.room.register_text_stream_handler(CART_TOPIC, _on_cart)
    except Exception as e:  # pragma: no cover - runtime only
        logger.debug("cart handler registration skipped: %s", e)

    # Start the session in the background
    logger.info("Starting AgentSession in background task...")
    session_task = asyncio.create_task(session.start(room=ctx.room, agent=agent))

    # Greet the user after a short delay to allow WebRTC tracks to bind
    logger.info("Waiting 1.5 seconds for WebRTC connection to bind...")
    await asyncio.sleep(1.5)
    await session.say(
        "Hi! Welcome to ShopMax. I can help you find products, check prices and availability, "
        "or track your orders. What would you like to do?"
    )

    # Keep the entrypoint running until the session terminates
    await session_task


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
