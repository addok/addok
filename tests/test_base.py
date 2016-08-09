from addok import config


def test_connection_port_is_not_default_one():
    assert config.DB.connection_pool.connection_kwargs['db'] == 15
