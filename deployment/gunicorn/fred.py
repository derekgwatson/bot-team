# Fred gunicorn configuration
import multiprocessing

# Server socket
bind = "127.0.0.1:8001"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/gunicorn-fred/access.log"
errorlog = "/var/log/gunicorn-fred/error.log"
loglevel = "info"

# Process naming
proc_name = "fred"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn-fred/fred.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if terminating SSL at gunicorn instead of nginx)
# keyfile = None
# certfile = None
