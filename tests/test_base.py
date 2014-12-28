from addok.core import DB


def test_connection_port_is_not_default_one():
    assert DB.connection_pool.connection_kwargs['db'] == 15
