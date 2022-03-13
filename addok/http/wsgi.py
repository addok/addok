import falcon

from addok.config import config, hooks

from .base import CorsMiddleware

config.load()
middlewares = [CorsMiddleware()]
hooks.register_http_middleware(middlewares)
# The name `application` is expected by wsgi by default.
application = api = falcon.App(middleware=middlewares)
# Do not let Falcon split query string on commas.
application.req_options.auto_parse_qs_csv = False
application.req_options.strip_url_path_trailing_slash = True
hooks.register_http_endpoint(api)


def simple(args):
    from wsgiref.simple_server import make_server

    httpd = make_server(args.host, int(args.port), application)
    print("Serving HTTP on {}:{}…".format(args.host, args.port))
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, EOFError):
        print("Bye!")
