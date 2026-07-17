# SENTINEL agent + glass-box UI in one container (Akash-deployable).
# The model is the Anthropic API — this container is the AGENT+UI runtime, not inference.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY loop_engine/ loop_engine/
COPY skins/ skins/
COPY sentinel/ sentinel/
EXPOSE 8787
# ANTHROPIC_API_KEY is injected at deploy time; without it SENTINEL runs
# with deterministic cached plans and says so in the UI.
CMD ["python", "-m", "sentinel.app"]
