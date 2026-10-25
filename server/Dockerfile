FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data
WORKDIR /app
COPY server/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r /app/requirements.lock.txt \
    && groupadd --gid 10001 ctf \
    && useradd --uid 10001 --gid ctf --no-create-home ctf \
    && mkdir /data \
    && chown ctf:ctf /data
COPY --chown=ctf:ctf server/ /app/server/
USER ctf
EXPOSE 8000
CMD ["python", "-m", "server.container"]
