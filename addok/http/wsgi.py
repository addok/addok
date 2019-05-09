try:
    from addok_http_falcon.main import api  # Legacy.
    application = api
except ImportError:
    try:
        from addok_http_roll import app  # Legacy.
        application = app
    except ImportError:
        print("Missing http plugin, try `pip install addok-http-falcon`")
