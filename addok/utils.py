from functools import wraps
from importlib import import_module
from math import asin, cos, exp, radians, sin, sqrt


def iter_pipe(pipe, processors):
    if isinstance(pipe, str):
        pipe = [pipe]
    for it in processors:
        pipe = it(pipe)
    yield from pipe


def import_by_path(path):
    """
    Import functions or class by their path. Should be of the form:
    path.to.module.func
    """
    module_path, name = path.rsplit('.', 1)
    module = import_module(module_path)
    attr = getattr(module, name)
    return attr


def yielder(func):
    @wraps(func)
    def wrapper(pipe):
        for item in pipe:
            yield func(item)
    return wrapper


def dumb_geo_distance(point1, point2):
    lat1, lon1 = point1
    lat2, lon2 = point2
    d = abs((lat2 - lat1) + (lon2 - lon1))
    return d


def haversine_distance(point1, point2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    """
    lat1, lon1 = point1
    lat2, lon2 = point2

    # Convert decimal degrees to radians.
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula.
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # 6367 km is the radius of the Earth.
    km = 6367 * c
    return km


def km_to_score(km):
    # Score between 0 and 0.1 (close to 0 km will be close to 0.1, and 100 and
    # above will be 0).
    return 0.0 if km > 100 else .1 * exp(-(km / 50.0) ** 2)
