from pathlib import Path

from addok.config import config
from addok.db import DB


@config.on_load
def load_scripts():
    root = Path(__file__).parent / "lua"
    for path in root.glob("*.lua"):
        with path.open() as f:
            name = path.name[:-4]
            globals()[name] = DB.register_script(f.read())
