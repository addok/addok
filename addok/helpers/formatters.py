def geojson(result):
    properties = {
        "label": str(result),
    }
    if result._scores:
        properties["score"] = result.score
    for key in result.keys:
        val = getattr(result, key, None)
        if val:
            properties[key] = val
    housenumber = getattr(result, 'housenumber', None)
    if housenumber:
        if result._doc.get('type'):
            properties[result._doc['type']] = properties.get('name')
        properties['name'] = '{} {}'.format(housenumber,
                                            properties.get('name'))
    try:
        properties['distance'] = int(result.distance)
    except ValueError:
        pass
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(result.lon), float(result.lat)]
        },
        "properties": properties,
        "id": result.id
    }
