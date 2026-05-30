import os

# The socket to bind to
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Number of worker processes
# (Rule of thumb: 2 x number of cores + 1)
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
if workers > 4:
    threads = 2
else:
    threads = 4
threads = int(os.getenv("GUNICORN_THREADS", str(threads)))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
max_requests = 100
max_requests_jitter = 200

print(f"Gunicorn starting with {workers} workers and {threads} threads per worker.")
print(f"Total theoretical concurrency: {workers * threads}")

# For "--preload" below:
# https://github.com/viniciuschiele/flask-apscheduler/issues/139#issuecomment-793291830=
preload = True
