FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system --gid 10001 designagent \
    && adduser --system --uid 10001 --gid 10001 --home /nonexistent --no-create-home designagent

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /app/requirements.txt

COPY --chown=10001:10001 app /app/app
COPY --chown=10001:10001 THIRD_PARTY_NOTICES.md /app/THIRD_PARTY_NOTICES.md

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--workers", "1", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
