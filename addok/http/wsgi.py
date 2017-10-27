from addok.config import config, hooks

from .base import app

config.load()
hooks.register_http_endpoint(app)
