import json
import zlib


class ZlibSerializer:
    @classmethod
    def dumps(cls, data):
        return zlib.compress(json.dumps(data).encode())

    @classmethod
    def loads(cls, data):
        return json.loads(zlib.decompress(data).decode())
