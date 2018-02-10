from addok.config import config
from addok.helpers import haversine_distance, km_to_score
from addok.helpers.text import ascii, compare_str, contains, equals, startswith


def make_labels(helper, result):
    if not result.labels:
        # Make your own for better scoring (see addok-france for inspiration).
        result.labels = result._rawattr(config.NAME_FIELD)[:]
        label = result.labels[0]
        city = getattr(result, 'city', None)
        if city and city != label:
            postcode = getattr(result, 'postcode', None)
            if postcode:
                label = '{} {}'.format(label, postcode)
            label = '{} {}'.format(label, city)
            result.labels.insert(0, label)
        housenumber = getattr(result, 'housenumber', None)
        if housenumber:
            label = '{} {}'.format(housenumber, label)
            result.labels.insert(0, label)


def match_housenumber(helper, result):
    _match_housenumber(helper, result, helper.tokens)


def _match_housenumber(helper, result, tokens):
    if not helper.check_housenumber:
        return
    # Housenumber may have multiple tokens (eg. "dix huit"), we join
    # those to match the way they have been processed by
    # addok.helpers.index.prepare_housenumbers.
    raw = ''.join(sorted(helper.housenumbers, key=lambda t: t.position))
    if raw and raw in result.housenumbers:
        data = result.housenumbers[str(raw)]
        result.housenumber = data.pop('raw')
        result.type = 'housenumber'
        result.update(data)


def score_by_importance(helper, result):
    importance = getattr(result, 'importance', None)
    importance = importance or 0.0
    result.add_score('importance',
                     float(importance) * config.IMPORTANCE_WEIGHT,
                     config.IMPORTANCE_WEIGHT)


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
            result.add_score('str_distance', score, ceiling=1.0)
            if score >= config.MATCH_THRESHOLD:
                break
    if not score:
        _score_by_str_distance(helper, result, scale=0.9)


def _score_by_str_distance(helper, result, scale=1.0):
    for label in result.labels:
        label = ascii(label)
        score = compare_str(label, helper.query) * scale
        result.add_score('str_distance', score, ceiling=1.0)
        if score >= config.MATCH_THRESHOLD:
            break


def score_by_str_distance(helper, result):
    if helper.autocomplete:
        return
    _score_by_str_distance(helper, result)


score_by_ngram_distance = score_by_str_distance  # Retrocompat.


def score_by_geo_distance(helper, result):
    if helper.lat is None or helper.lon is None:
        return
    km = haversine_distance((float(result.lat), float(result.lon)),
                            (helper.lat, helper.lon))
    result.distance = km * 1000
    result.add_score('geo_distance', km_to_score(km), ceiling=0.1)


def load_closer(helper, result):
    if not helper.check_housenumber:
        return

    def sort(h):
        return haversine_distance((float(h['lat']), float(h['lon'])),
                                  (helper.lat, helper.lon))

    candidates = []
    if result.housenumbers:
        candidates = list(result.housenumbers.values())
    candidates.append({'raw': None, 'lat': result.lat, 'lon': result.lon})
    candidates.sort(key=sort)
    closer = candidates[0]
    if closer['raw']:  # Means a housenumber is closer than street center.
        result.housenumber = closer.pop('raw')
        result.type = 'housenumber'
        result.update(closer)
