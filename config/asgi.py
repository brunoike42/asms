"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

#import os

#from django.core.asgi import get_asgi_application

#os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

#application = get_asgi_application()

# asgi.py
#from transport.consumers import RouteTrackingConsumer
#websocket_urlpatterns += [
#    re_path(r"ws/transport/route/(?P<route_id>\d+)/$", RouteTrackingConsumer.as_asgi()),
#]

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

import apps.transport.routing  # import AFTER get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            apps.transport.routing.websocket_urlpatterns
        )
    ),
})