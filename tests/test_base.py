from pathlib import Path
import os

import pytest

from addok import db, ds


def test_connection_port_is_not_default_one():
    assert db.DB.connection_pool.connection_kwargs["db"] == 14
    assert ds._DB.connection_pool.connection_kwargs["db"] == 15


def test_config_on_load_is_called_on_config_load():
    from addok.config import Config

    config = Config()

    @config.on_load
    def on_load():
        on_load.called = True

    config.load()
    assert on_load.called

    on_load.called = False

    # config should not reload if already loaded.
    config.load()
    assert not on_load.called


def test_local_config_has_been_loaded(config):
    # See addok/config/test.py
    assert config.COMMON_THRESHOLD == 1000


def test_config_does_not_fail_if_local_path_does_not_exist(capsys):
    os.environ["ADDOK_CONFIG_MODULE"] = "dummy/path.py"
    from addok.config import Config

    config = Config()
    config.load()
    out, err = capsys.readouterr()
    assert "No local config file found" in out
    os.environ["ADDOK_CONFIG_MODULE"] = ""


def test_config_load_exit_if_local_file_is_invalid():
    path = str(Path(__file__).parent / "invalid_config.py")
    os.environ["ADDOK_CONFIG_MODULE"] = path
    from addok.config import Config

    config = Config()
    with pytest.raises(SystemExit) as err:
        config.load()
        assert "Unable to import" in err
    os.environ["ADDOK_CONFIG_MODULE"] = ""


def test_config_on_load_consume_env_vars():
    from addok.config import Config

    os.environ["ADDOK_BATCH_WORKERS"] = "13"
    config = Config()

    config.load()
    assert config.BATCH_WORKERS == 13
