"""Tests for multiprocessing helpers."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from addok.config import config
from addok.helpers import _get_config_overrides, _worker_init


def test_get_config_overrides_detects_changed_values():
    """Test that _get_config_overrides detects configuration changes."""
    # Modify a config value
    original_value = config.MIN_EDGE_NGRAMS
    config.MIN_EDGE_NGRAMS = 99

    try:
        overrides = _get_config_overrides()

        # Should detect the change
        assert 'MIN_EDGE_NGRAMS' in overrides
        assert overrides['MIN_EDGE_NGRAMS'] == 99
    finally:
        # Restore original value
        config.MIN_EDGE_NGRAMS = original_value


def test_get_config_overrides_skips_unchanged_values():
    """Test that unchanged values are not included in overrides."""
    overrides = _get_config_overrides()

    # BUCKET_MIN should not be in overrides if it hasn't changed from default
    # (unless it was changed in test config)
    from addok.config import default as default_config

    if config.BUCKET_MIN == default_config.BUCKET_MIN:
        assert 'BUCKET_MIN' not in overrides


def test_get_config_overrides_skips_functions():
    """Test that functions are filtered out from overrides."""
    # Set a function as a config value
    def dummy_func():
        pass

    config.TEST_FUNCTION = dummy_func

    # Functions should be filtered out
    overrides = _get_config_overrides()
    assert 'TEST_FUNCTION' not in overrides

    # Clean up
    del config['TEST_FUNCTION']


def test_get_config_overrides_skips_classes():
    """Test that classes are filtered out from overrides."""
    class DummyClass:
        pass

    config.TEST_CLASS = DummyClass

    # Classes should be filtered out
    overrides = _get_config_overrides()
    assert 'TEST_CLASS' not in overrides

    # Clean up
    del config['TEST_CLASS']


def test_get_config_overrides_includes_serializable_values():
    """Test that serializable values are included."""
    config.TEST_STRING = "test_value"
    config.TEST_INT = 42
    config.TEST_BOOL = True
    config.TEST_LIST = [1, 2, 3]
    config.TEST_DICT = {"key": "value"}

    try:
        overrides = _get_config_overrides()

        # All these should be included (if different from defaults)
        from addok.config import default as default_config

        if not hasattr(default_config, 'TEST_STRING'):
            assert overrides.get('TEST_STRING') == "test_value"
        if not hasattr(default_config, 'TEST_INT'):
            assert overrides.get('TEST_INT') == 42
        if not hasattr(default_config, 'TEST_BOOL'):
            assert overrides.get('TEST_BOOL') is True
        if not hasattr(default_config, 'TEST_LIST'):
            assert overrides.get('TEST_LIST') == [1, 2, 3]
        if not hasattr(default_config, 'TEST_DICT'):
            assert overrides.get('TEST_DICT') == {"key": "value"}
    finally:
        # Clean up
        for key in ['TEST_STRING', 'TEST_INT', 'TEST_BOOL', 'TEST_LIST', 'TEST_DICT']:
            if key in config:
                del config[key]


@patch('addok.helpers.os.environ', {})
def test_worker_init_sets_environment_variables():
    """Test that _worker_init sets environment variables."""
    env_vars = {'TEST_VAR': 'test_value'}
    redis_params = {
        'indexes': {'host': 'localhost', 'port': 6379, 'db': 0},
        'documents': {'host': 'localhost', 'port': 6379, 'db': 1},
        'use_redis_documents': False
    }

    with patch('addok.db.DB.connect') as mock_connect:
        _worker_init(redis_params, config_env_vars=env_vars)

        assert os.environ.get('TEST_VAR') == 'test_value'
        mock_connect.assert_called_once()


def test_worker_init_applies_config_overrides():
    """Test that _worker_init applies configuration overrides."""
    redis_params = {
        'indexes': {'host': 'localhost', 'port': 6379, 'db': 0},
        'documents': {'host': 'localhost', 'port': 6379, 'db': 1},
        'use_redis_documents': False
    }
    overrides = {'MIN_EDGE_NGRAMS': 99}

    original_value = config.MIN_EDGE_NGRAMS

    try:
        with patch('addok.db.DB.connect'):
            _worker_init(redis_params, config_overrides=overrides)

            # Config should be updated
            assert config.MIN_EDGE_NGRAMS == 99
    finally:
        # Restore
        config.MIN_EDGE_NGRAMS = original_value


def test_worker_init_connects_to_redis():
    """Test that _worker_init connects to Redis."""
    redis_params = {
        'indexes': {'host': 'localhost', 'port': 6379, 'db': 14},
        'documents': {'host': 'localhost', 'port': 6379, 'db': 15},
        'use_redis_documents': True
    }

    with patch('addok.db.DB.connect') as mock_db_connect:
        with patch('addok.ds._DB.connect') as mock_ds_connect:
            _worker_init(redis_params)

            # Should connect to both databases
            mock_db_connect.assert_called_once_with(
                host='localhost', port=6379, db=14
            )
            mock_ds_connect.assert_called_once_with(
                host='localhost', port=6379, db=15
            )


def test_worker_init_skips_document_store_if_not_redis():
    """Test that document store connection is skipped when not using Redis."""
    redis_params = {
        'indexes': {'host': 'localhost', 'port': 6379, 'db': 14},
        'documents': {'host': 'localhost', 'port': 6379, 'db': 15},
        'use_redis_documents': False
    }

    with patch('addok.db.DB.connect') as mock_db_connect:
        with patch('addok.ds._DB.connect') as mock_ds_connect:
            _worker_init(redis_params)

            # Should only connect to indexes DB
            mock_db_connect.assert_called_once()
            mock_ds_connect.assert_not_called()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_parallelize_uses_spawn_on_macos():
    """Test that parallelize uses spawn context on macOS."""
    from addok.helpers import parallelize

    def dummy_func(*items):
        return items

    # This is a smoke test - just ensure it doesn't crash
    # We can't easily test the actual multiprocessing without mocking
    with patch('addok.helpers.ChunkedPool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool.return_value.__enter__ = MagicMock(return_value=mock_pool_instance)
        mock_pool.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_instance.imap_unordered.return_value = []

        parallelize(dummy_func, [], chunk_size=10)

        # Verify spawn context was requested on macOS
        from multiprocessing import get_context
        mock_pool.assert_called_once()
        call_kwargs = mock_pool.call_args[1]
        assert 'context' in call_kwargs
        # Context should be spawn on macOS
        assert call_kwargs['context']._name == 'spawn'


@pytest.mark.skipif(sys.platform == "darwin", reason="Linux-specific test")
def test_parallelize_uses_fork_on_linux():
    """Test that parallelize uses fork context on Linux."""
    from addok.helpers import parallelize

    def dummy_func(*items):
        return items

    with patch('addok.helpers.ChunkedPool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool.return_value.__enter__ = MagicMock(return_value=mock_pool_instance)
        mock_pool.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool_instance.imap_unordered.return_value = []

        parallelize(dummy_func, [], chunk_size=10)

        # Verify fork context was requested on Linux
        mock_pool.assert_called_once()
        call_kwargs = mock_pool.call_args[1]
        assert 'context' in call_kwargs
        # Context should be fork on Linux
        assert call_kwargs['context']._name == 'fork'
