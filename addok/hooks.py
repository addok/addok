import pluggy

spec = pluggy.HookspecMarker('addok')
register = pluggy.HookimplMarker('addok')


@spec
def addok_register_http_endpoints(endpoints):
    """Add new endpoints to Addok API."""
    pass


@spec
def addok_preconfigure(config):
    """Configure addok by patching config object before user local config."""


@spec
def addok_configure(config):
    """Configure addok by patching config object after user local config."""


@spec
def addok_register_command(subparsers):
    """Register command for Addok CLI."""
