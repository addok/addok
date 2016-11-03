from addok.db import DB


def test_connection_port_is_not_default_one():
    assert DB.connection_pool.connection_kwargs['db'] == 15


def test_config_on_load_is_called_on_config_load():
    from addok.config import Config
    config = Config()

    @config.on_load
    def on_load():
        on_load.called = True

    config.load()
    assert on_load.called
