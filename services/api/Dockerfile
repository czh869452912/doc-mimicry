FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app/services/api:/app/packages/contracts:/app/packages/workspace:/app/packages/timeline:/app/tools/import:/app/agent/runtime-adapters/mock:/app/agent/runtime-adapters/openhands

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ARCHITECTURE.md ./
COPY services/api ./services/api
COPY packages ./packages
COPY agent/runtime-adapters ./agent/runtime-adapters
COPY agent/system-prompts ./agent/system-prompts
COPY agent/skills ./agent/skills
COPY tools ./tools
COPY doc-types ./doc-types

RUN pip install --no-cache-dir -e ".[openhands]"

CMD ["uvicorn", "--factory", "docagent_api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
