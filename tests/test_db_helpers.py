"""Tests for Redis database helpers."""
from addok.db import _extract_redis_config, get_redis_params


def test_extract_redis_config_with_all_params():
    """Test extraction of Redis config with all parameters."""
    config_section = {
        "host": "redis.example.com",
        "port": 6380,
        "db": 5,
        "password": "secret123",
        "unix_socket_path": "/var/run/redis.sock",
    }

    result = _extract_redis_config(config_section)

    assert result["host"] == "redis.example.com"
    assert result["port"] == 6380
    assert result["db"] == 5
    assert result["password"] == "secret123"
    assert result["unix_socket_path"] == "/var/run/redis.sock"


def test_extract_redis_config_with_minimal_params():
    """Test extraction with minimal parameters."""
    config_section = {
        "host": "localhost",
        "port": 6379,
        "db": 0,
    }

    result = _extract_redis_config(config_section)

    assert result["host"] == "localhost"
    assert result["port"] == 6379
    assert result["db"] == 0
    assert result["password"] is None
    assert result["unix_socket_path"] is None


def test_extract_redis_config_handles_missing_keys():
    """Test extraction handles missing keys gracefully."""
    config_section = {}

    result = _extract_redis_config(config_section)

    assert result["host"] is None
    assert result["port"] is None
    assert result["db"] is None
    assert result["password"] is None
    assert result["unix_socket_path"] is None


def test_get_redis_params_returns_structured_dict():
    """Test that get_redis_params returns properly structured dict."""
    result = get_redis_params()

    # Should have the three main keys
    assert "indexes" in result
    assert "documents" in result
    assert "use_redis_documents" in result

    # Each should be a dict with connection params
    assert isinstance(result["indexes"], dict)
    assert isinstance(result["documents"], dict)
    assert isinstance(result["use_redis_documents"], bool)

    # Should have standard Redis connection keys
    for key in ["host", "port", "db", "password", "unix_socket_path"]:
        assert key in result["indexes"]
        assert key in result["documents"]


def test_get_redis_params_uses_config_values(config):
    """Test that get_redis_params uses values from config."""
    # Test config should have specific database numbers
    result = get_redis_params()

    # In test environment, databases should be 14 and 15
    assert result["indexes"]["db"] == 14
    assert result["documents"]["db"] == 15


def test_get_redis_params_detects_redis_document_store(config):
    """Test detection of Redis as document store."""
    from addok import ds
    from addok.config import config as addok_config

    result = get_redis_params()

    # Should correctly identify if using Redis for documents
    expected = addok_config.DOCUMENT_STORE == ds.RedisStore
    assert result["use_redis_documents"] == expected
