import redis
from addok.config import config


class RedisProxy:
    instance = None
    Error = redis.RedisError

    def connect(self, *args, **kwargs):
        self.instance = redis.StrictRedis(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def stats(self, patterns):
        for pattern in patterns:
            total = 0
            for k in self.scan_iter(pattern):
                total += self.debug_object(k)['serializedlength']
            yield pattern, total


DB = RedisProxy()


@config.on_load
def connect():
    params = config.REDIS.copy()
    params.update(config.REDIS.get('indexes', {}))
    DB.connect(host=params['host'], port=params['port'], db=params['db'])
