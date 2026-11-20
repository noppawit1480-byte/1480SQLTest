FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# var/ holds the SQLite engine's databases (mounted as a volume in compose)
RUN useradd --create-home --uid 10001 app && mkdir -p /app/var/sqlite && chown -R app /app
USER app
EXPOSE 8000
# migrations + idempotent seed (also provisions the sandbox) before serving
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers"]
