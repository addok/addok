from addok import db, ds


def test_connection_port_is_not_default_one():
    assert db.DB.connection_pool.connection_kwargs['db'] == 14
    assert ds._DB.connection_pool.connection_kwargs['db'] == 15


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
