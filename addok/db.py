import redis


class DBRedis:
    instance = None

    def connect(self, *args, **kwargs):
        self.instance = redis.StrictRedis(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.instance, name)

DB = DBRedis()
