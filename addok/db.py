import redis

from . import config

DB = redis.StrictRedis(**config.DB_SETTINGS)
