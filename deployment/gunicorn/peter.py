# Peter gunicorn configuration
import multiprocessing

# Server socket
bind = "127.0.0.1:8003"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "/var/log/peter/access.log"
errorlog = "/var/log/peter/error.log"
loglevel = "info"

# Process naming
proc_name = "peter"

# Server mechanics
daemon = False
pidfile = "/var/run/peter/peter.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None
