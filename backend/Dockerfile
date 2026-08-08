FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 deltracking \
    && useradd --uid 10001 --gid deltracking --no-create-home --shell /usr/sbin/nologin deltracking

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
RUN python -m pip install --no-cache-dir .

COPY docker-entrypoint.sh /usr/local/bin/deltracking-entrypoint
RUN chmod 0555 /usr/local/bin/deltracking-entrypoint \
    && mkdir -p /data \
    && chown deltracking:deltracking /data

USER deltracking

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/deltracking-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
