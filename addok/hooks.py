import pluggy

spec = pluggy.HookspecMarker('addok')
register = pluggy.HookimplMarker('addok')


@spec
def addok_register_http_endpoints(endpoints):
    """Add new endpoints to Addok API."""
    pass


@spec
def addok_configure(config):
    """Configure addok by patching config object."""


@spec
def addok_register_search_steps(helper):
    """Add search step."""


@spec
def addok_register_command(subparsers):
    """Register command for Addok CLI."""
