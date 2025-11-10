# 🏠 Addok

**A blazing fast address search engine. Made for addresses, optimized for addresses, nothing but addresses.**

Addok is a powerful geocoding engine that indexes your address data and exposes it through a clean HTTP API. Built with performance in mind, it handles typos, autocomplete, and filters with ease.

[![PyPi version](https://img.shields.io/pypi/v/addok.svg)](https://pypi.python.org/pypi/addok/)
[![Coverage Status](https://coveralls.io/repos/addok/addok/badge.svg?branch=main&service=github)](https://coveralls.io/github/addok/addok?branch=main)

**Requirements:** Python 3.9–3.14 • Redis 7.2–8.0

---

## ✨ Features

- 🚀 **Fast**: Handles thousands of requests per second
- 🔍 **Smart search**: Fuzzy matching, typo-tolerant, autocomplete
- 🌍 **Geocoding & Reverse geocoding**: From text to coordinates and back
- 📦 **Batch processing**: Import and geocode CSV files
- 🔌 **Extensible**: Plugin system for custom needs
- 🎯 **Filtered search**: Query by postcode, city, region, or custom filters
- 🗺️ **Geographic bias**: Prioritize results near a location
- 🛠️ **Debug shell**: Interactive shell for testing and debugging
- 📊 **GeoJSON output**: Standard compliant API responses

---

## 🎬 Quick Example

Once installed and your data imported, searching for an address is as simple as:

```bash
curl "http://localhost:7878/search/?q=baker+street+221b"
```

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-0.158434, 51.523767]
      },
      "properties": {
        "label": "221B Baker Street, London NW1 6XE",
        "score": 0.95,
        "housenumber": "221B",
        "street": "Baker Street",
        "postcode": "NW1 6XE",
        "city": "London"
      }
    }
  ]
}
```

---

## 🚀 Getting Started

### Installation

```bash
pip install addok
```

### Import your data

```bash
addok batch your_addresses.ndjson
addok ngrams
```

### Start the server

```bash
addok serve
```

Your API is now running at `http://localhost:7878` 🎉

Check out the [full documentation](http://addok.readthedocs.org/en/latest/) for detailed instructions, configuration options, and advanced features.

---

## 🔌 Plugins

Extend Addok with plugins for your specific needs:

- **[addok-fr](https://github.com/addok/addok-fr)**: French language support
- **[addok-csv](https://github.com/addok/addok-csv)**: Batch CSV geocoding via HTTP
- **[addok-trigrams](https://github.com/addok/addok-trigrams)**: Trigram-based indexing
- **[addok-sqlite-store](https://github.com/addok/addok-sqlite-store)**: SQLite storage backend
- **[addok-psql](https://github.com/addok/addok-psql)**: PostgreSQL storage backend

[Discover all plugins](http://addok.readthedocs.io/en/latest/plugins/)

---

## 🌟 Production Ready

Addok powers the official French national address database with:
- **26+ million addresses** indexed
- **~2000 searches/second** throughput
- **~15 minutes** full import time

👉 [See it in action](http://adresse.data.gouv.fr/map) with the French address database demo

---

## 💡 Learn More

- 📖 [Documentation](http://addok.readthedocs.org/en/latest/)
- 🎓 [Tutorial](http://addok.readthedocs.org/en/latest/tutorial/)
- 💬 [Community Forum](https://forum.geocommuns.fr/c/adresses/addok-le-geocodeur/17) (French & English welcome)
- 🐛 [Report an issue](https://github.com/addok/addok/issues)

---

## 📄 License

Addok is released under the **MIT License**. Free to use, modify, and distribute.
