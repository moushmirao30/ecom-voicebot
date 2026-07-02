FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cache Silero VAD + TurnDetector weights into the image so cold starts
# don't download models at job time.
RUN python -m livekit.agents download-files

CMD ["python", "agent.py", "start"]
