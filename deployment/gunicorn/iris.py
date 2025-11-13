# Iris gunicorn configuration
import multiprocessing

# Server socket
bind = "127.0.0.1:8002"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/gunicorn-iris/access.log"
errorlog = "/var/log/gunicorn-iris/error.log"
loglevel = "info"

# Process naming
proc_name = "iris"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn-iris/iris.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None
