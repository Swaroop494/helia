FROM python:3.12.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /opt/helia
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock
COPY src/helia/executor/worker.py src/helia/executor/helia_plugin.py ./
# Derive target images and install their hash-pinned dependencies at BUILD time.
# No package installation or network access occurs during test execution.
USER 65534:65534
WORKDIR /work

