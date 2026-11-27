FROM python:3.14-alpine@sha256:5862d971d1f0ae26b258cefa4e893556b1d3aba81bd2ff30888704ad378bab67

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.lock ./
RUN apk add --no-cache libcrypto3=3.5.9-r1 libssl3=3.5.9-r1 zlib=1.4-r0
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock \
    && python -m pip uninstall --yes pip

COPY __init__.py __main__.py camera_socket.py http_api.py ./backend/
USER 10001:10001

EXPOSE 8080
CMD ["python", "-m", "backend", "--api"]
