FROM python:3.12.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/apps
RUN apt-get update && apt-get install -y gettext && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps ./apps 
COPY config ./config
COPY templates ./templates
COPY locale ./locale
COPY static ./static
COPY gunicorn.conf.py ./gunicorn.conf.py
COPY entry_point.sh ./entry_point.sh
COPY manage.py ./manage.py

RUN chmod +x /app/entry_point.sh

EXPOSE 8000

CMD ["/app/entry_point.sh"]
# CMD ["sh", "-c", "while true; do sleep 30; done"]
