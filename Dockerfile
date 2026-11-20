FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /football-web

RUN groupadd --system app && useradd --system --gid app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

USER app
EXPOSE 5001
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:5001", "--timeout", "60", "wsgi:app"]
