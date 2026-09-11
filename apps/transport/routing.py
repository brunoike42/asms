from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/transport/vehicle/(?P<vehicle_id>[\w-]+)/$', consumers.VehicleTrackingConsumer.as_asgi()),
    re_path(r'ws/transport/dashboard/(?P<tenant_id>[\w-]+)/$', consumers.FleetDashboardConsumer.as_asgi()),
]