FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system .
RUN mkdir -p /app/data /root/.cache/huggingface
EXPOSE 8080
CMD ["sh", "-c", "uvicorn smart_irrigation.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
