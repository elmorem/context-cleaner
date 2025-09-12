# Gunicorn Configuration for Context Cleaner Dashboard
# Production-ready WSGI server configuration

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8081"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "context_cleaner_dashboard"

# Server mechanics
daemon = False
pidfile = "/tmp/context_cleaner_dashboard.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (uncomment and configure for HTTPS)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment
raw_env = [
    "FLASK_ENV=production",
    "CLAUDE_CODE_ENABLE_TELEMETRY=1",
]

# Preload application for better memory usage
preload_app = True

# Hook functions for lifecycle management
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Context Cleaner Dashboard starting...")

def on_reload(server):
    """Called when a worker is reloaded."""
    server.log.info("Worker reloaded")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received SIGINT or SIGQUIT")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    worker.log.info("Worker initialized")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Server is ready. Spawning workers")

def worker_exit(server, worker):
    """Called just after a worker has been exited, in the master process."""
    server.log.info("Worker exited (pid: %s)", worker.pid)

def nworkers_changed(server, new_value, old_value):
    """Called when the number of workers is changed."""
    server.log.info("Number of workers changed from %s to %s", old_value, new_value)

def on_exit(server):
    """Called just before exiting."""
    server.log.info("Context Cleaner Dashboard shutting down...")