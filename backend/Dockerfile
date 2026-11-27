FROM python:3.14-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY __init__.py __main__.py camera_socket.py http_api.py ./backend/
USER 10001:10001

EXPOSE 8080
CMD ["python", "-m", "backend", "--api"]
