FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG INSTALL_DEV_DEPENDENCIES=false

RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
RUN pip install --upgrade pip && \
    if [ "$INSTALL_DEV_DEPENDENCIES" = "true" ]; then \
        pip install ".[dev]"; \
    else \
        pip install .; \
    fi

USER app
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "app.wsgi:app"]
