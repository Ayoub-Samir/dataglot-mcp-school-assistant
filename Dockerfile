FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY school_mcp ./school_mcp
COPY config ./config
COPY tests ./tests

ENTRYPOINT ["python", "-m", "school_mcp.server"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
