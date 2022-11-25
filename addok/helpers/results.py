from addok.config import config
from addok.helpers import haversine_distance, km_to_score
from addok.helpers.text import (
    ascii,
    compare_ngrams,
    compare_str,
    contains,
    equals,
    startswith,
)


def make_labels(helper, result):
    if not result.labels:
        # Make your own for better scoring (see addok-france for inspiration).
        result.labels = result._rawattr(config.NAME_FIELD)[:]
        label = result.labels[0]
        city = getattr(result, "city", None)
        if city and city != label:
            postcode = getattr(result, "postcode", None)
            if postcode:
                label = label + " " + postcode
            label = label + " " + city
        housenumber = getattr(result, "housenumber", None)
        if housenumber:
            label = "{} {}".format(housenumber, label)
        # Replace default label with our computed one, but keep the other raw
        # aliases, and let plugins add more of them if needed.
        result.labels[0] = label


def match_housenumber(helper, result):
    if not helper.check_housenumber:
        return
    # Housenumber may have multiple tokens (eg. "dix huit"), we join
    # those to match the way they have been processed by
    # addok.helpers.index.prepare_housenumbers.
    raw = "".join(sorted(helper.housenumbers, key=lambda t: t.position))
    if raw and raw in result.housenumbers:
        data = result.housenumbers[str(raw)]
        result.housenumber = data.pop("raw")
        result.type = "housenumber"
        result.update(data)
    if helper.only_housenumber and not result.housenumber:
        helper.debug(
            "Cannot match housenumber (%s), removing `%s`", result.housenumber, result
        )
        return False


def score_by_importance(helper, result):
    importance = getattr(result, "importance", None) or 0.0
    result.add_score(
        "importance",
        float(importance) * config.IMPORTANCE_WEIGHT,
        config.IMPORTANCE_WEIGHT,
    )


def score_by_autocomplete_distance(helper, result):
    if not helper.autocomplete:
        return
    score = 0
    query = ascii(helper.query)
    for idx, label in enumerate(result.labels):
        label = ascii(label)
        result.labels[idx] = label  # Cache ascii folding.
        if equals(query, label):
            score = 1.0
        elif startswith(query, label):
            score = 0.9
        elif contains(query, label):
            score = 0.7
        if score:
            result.add_score("str_distance", score, ceiling=1.0)
    if not score:
        _score_by_ngram_distance(helper, result, scale=0.9)


def _score_by_str_distance(helper, result, scale=1.0):
    for label in result.labels:
        score = compare_str(label, helper.query) * scale
        result.add_score("str_distance", score, ceiling=1.0)


def score_by_str_distance(helper, result):
    if helper.autocomplete:
        return
    _score_by_str_distance(helper, result)


def _score_by_ngram_distance(helper, result, scale=1.0):
    for label in result.labels:
        label = ascii(label)
        score = compare_ngrams(label, helper.query) * scale
        result.add_score("str_distance", score, ceiling=1.0)
        if score >= config.MATCH_THRESHOLD:
            break


def score_by_ngram_distance(helper, result):
    if helper.autocomplete:
        return
    _score_by_ngram_distance(helper, result)


def score_by_geo_distance(helper, result):
    if helper.lat is None or helper.lon is None:
        return
    km = haversine_distance(
        (float(result.lat), float(result.lon)), (helper.lat, helper.lon)
    )
    result.distance = km * 1000
    result.add_score(
        "geo_distance",
        km_to_score(km) * config.GEO_DISTANCE_WEIGHT,
        ceiling=config.GEO_DISTANCE_WEIGHT,
    )


def adjust_scores(helper, result):
    if helper.lat is not None and helper.lon is not None:
        str_distance = result._scores.get("str_distance")
        if str_distance:
            result._scores["str_distance"] = (str_distance[0] * 0.9, str_distance[1])
        importance = result._scores.get("importance")
        if importance:
            result._scores["importance"] = (importance[0] * 0.1, importance[1])


def load_closer(helper, result):
    if not helper.check_housenumber:
        return

    def sort(h):
        return haversine_distance(
            (float(h["lat"]), float(h["lon"])), (helper.lat, helper.lon)
        )

    candidates = []
    if result.housenumbers:
        candidates = list(result.housenumbers.values())
    if not helper.only_housenumber:
        candidates.append({"raw": None, "lat": result.lat, "lon": result.lon})
    candidates.sort(key=sort)
    closer = candidates[0]
    if closer["raw"]:  # Means a housenumber is closer than street center.
        result.housenumber = closer.pop("raw")
        result.type = "housenumber"
        result.update(closer)
    if helper.only_housenumber and not result.housenumber:
        helper.debug("Removing non housenumber match `%s`", result)
        return False
