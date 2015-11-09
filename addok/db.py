import redis

from . import config

DB = redis.StrictRedis(**config.REDIS)
