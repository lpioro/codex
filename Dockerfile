FROM python:3.12-slim-bookworm AS test
WORKDIR /app
COPY server/ server/
COPY tests/ tests/
COPY scripts/package_extension.py scripts/package_extension.py
COPY extension/ extension/
RUN python -m unittest discover -s tests -v

FROM python:3.12-slim-bookworm AS runtime
LABEL org.opencontainers.image.title="WalleeGuard" \
      org.opencontainers.image.description="Private AI prompt collector, browser endpoint management and security dashboard" \
      org.opencontainers.image.source="https://github.com/lpioro/codex"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8787 \
    PROMPT_DB=/data/prompts.sqlite3
WORKDIR /app
RUN groupadd --gid 10001 promptobs \
    && useradd --uid 10001 --gid 10001 --no-create-home promptobs \
    && mkdir /data && chown 10001:10001 /data && chmod 0700 /data
COPY --from=test --chown=10001:10001 /app/server/ server/
USER 10001:10001
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8787/health',timeout=3); assert json.load(r)=={'status':'ok'}"
CMD ["python", "-m", "server.app"]
