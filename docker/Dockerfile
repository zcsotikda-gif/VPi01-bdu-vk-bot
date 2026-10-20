# Образ для тестов: VK и LLM в тестах замоканы, сеть и .env не нужны.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[dev]"

COPY tests ./tests
CMD ["pytest", "-q"]
