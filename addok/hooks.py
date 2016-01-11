import pluggy

spec = pluggy.HookspecMarker('addok')
register = pluggy.HookimplMarker('addok')


@spec
def addok_register_http_endpoints(endpoints):
    """Add new endpoints to Addok API."""
    pass


@spec
def addok_register_string_processors(processors):
    """Add string processors."""


@spec
def addok_register_housenumber_processors(processors):
    """Add processors for housenumber field."""


@spec
def addok_register_query_processors(processors):
    """Add query processors."""


@spec
def addok_register_batch_processors(processors):
    """Add processors for batch import."""


@spec
def addok_register_search_steps(helper):
    """Add search step."""


@spec
def addok_register_command(subparsers):
    """Register command for Addok CLI."""
