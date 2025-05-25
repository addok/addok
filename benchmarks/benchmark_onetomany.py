import random
import time
from addok.helpers.collectors import _compute_onetomany_relations
from addok.helpers.text import Token
import addok.helpers.collectors as collectors

class FakeDB:
    def __init__(self, tokens, ratio=0.1):
        self.pairs = set()
        for token in tokens:
            for other in tokens:
                if token == other:
                    continue
                if random.random() < ratio:
                    self.pairs.add((str(token), str(other)))

    def smembers(self, key):
        token = key.split("|", 1)[1]
        return [other.encode() for t, other in self.pairs if t == token]

# Number of tokens can be adjusted to mimic realistic queries
TOKEN_COUNT = 50
ITERATIONS = 100

tokens = [Token(str(i)) for i in range(TOKEN_COUNT)]

fake_db = FakeDB(tokens)

DB_backup = collectors.DB
try:
    # Monkey patch DB with fake one
    import types
    collectors.DB = types.SimpleNamespace(smembers=fake_db.smembers)
    start = time.perf_counter()
    for _ in range(ITERATIONS):
        _compute_onetomany_relations(tokens)
    duration = time.perf_counter() - start
    print(f"{ITERATIONS} runs in {duration:.4f}s ({TOKEN_COUNT} tokens)")
finally:
    collectors.DB = DB_backup
