# Legacy import.
try:
    from addok_http_falcon import View, log_notfound, log_query  # noqa
except ImportError:
    print('Falcon http not installed, please type "pip install addok-http-falcon"')
