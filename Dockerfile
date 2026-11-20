FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LEDGERFORGE_DATA=/app/seed \
    LEDGERFORGE_DB=/var/lib/ledgerforge/ledgerforge.sqlite \
    LEDGERFORGE_STATE_DIR=/var/lib/ledgerforge

WORKDIR /app

COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN useradd --create-home --uid 1001 appuser \
    && mkdir -p /var/lib/ledgerforge \
    && chown -R appuser:appuser /var/lib/ledgerforge /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

CMD ["python", "-m", "scripts.entrypoint"]
