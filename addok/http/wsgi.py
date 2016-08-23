import falcon

from addok.config import config, hooks

from .base import CorsMiddleware

config.load()
middlewares = [CorsMiddleware()]
hooks.register_api_middleware(middlewares)
application = falcon.API(middleware=middlewares)
hooks.register_api_endpoint(application)


def simple(args):
    from wsgiref.simple_server import make_server
    httpd = make_server(args.host, int(args.port), application)
    print("Serving HTTP on {}:{}…".format(args.host, args.port))
    try:
        httpd.serve_forever()
    except (KeyboardInterrupt, EOFError):
        print('Bye!')
