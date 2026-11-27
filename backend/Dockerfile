FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.lock ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends libzstd1=1.5.7+dfsg-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock \
    && python -m pip uninstall --yes pip

COPY __init__.py __main__.py camera_socket.py http_api.py ./backend/
USER 10001:10001

EXPOSE 8080
CMD ["python", "-m", "backend", "--api"]
