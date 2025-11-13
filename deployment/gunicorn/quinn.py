# Quinn gunicorn configuration
import multiprocessing

# Server socket
bind = "127.0.0.1:8005"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/quinn/access.log"
errorlog = "/var/log/quinn/error.log"
loglevel = "info"

# Process naming
proc_name = "quinn"

# Server mechanics
daemon = False
pidfile = "/var/run/quinn/quinn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None
