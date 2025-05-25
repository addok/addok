VERSION = None

from importlib.metadata import version, PackageNotFoundError

if __package__:
    try:
        VERSION = version(__package__)
    except PackageNotFoundError:
        VERSION = None
