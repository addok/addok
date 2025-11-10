import redis
from hashids import Hashids

from addok.config import config


hashids = Hashids()


class RedisProxy:
    instance = None
    Error = redis.RedisError

    def connect(self, *args, **kwargs):
        self.instance = redis.Redis(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def next_id(self):
        next_id = self.incr("_id_sequence")
        return hashids.encode(next_id)


DB = RedisProxy()


def _extract_redis_config(config_section):
    """Extract Redis connection parameters from a config section.

    Args:
        config_section: Dict with Redis configuration

    Returns:
        Dict with connection parameters
    """
    return {
        "host": config_section.get("host"),
        "port": config_section.get("port"),
        "db": config_section.get("db"),
        "password": config_section.get("password"),
        "unix_socket_path": config_section.get("unix_socket_path"),
    }


def get_redis_params():
    """Extract Redis connection parameters from config for multiprocessing workers.

    Returns:
        Dict with separate connection parameters for indexes and documents databases.
    """
    from addok import ds

    # Get indexes (main DB) parameters
    indexes_params = config.REDIS.copy()
    indexes_params.update(config.REDIS.get("indexes", {}))

    # Get documents DB parameters
    documents_params = config.REDIS.copy()
    documents_params.update(config.REDIS.get("documents", {}))

    return {
        "indexes": _extract_redis_config(indexes_params),
        "documents": _extract_redis_config(documents_params),
        "use_redis_documents": config.DOCUMENT_STORE == ds.RedisStore,
    }


@config.on_load
def connect():
    params = get_redis_params()
    DB.connect(**params['indexes'])
