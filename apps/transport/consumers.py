"""
WebSocket consumer for live bus tracking. Reuses the same Django Channels + Redis channel
layer already in the stack (Section 13) for attendance/payment real-time updates — no new
real-time technology is introduced.

Wire this into your existing asgi.py routing, e.g.:

    from transport.consumers import RouteTrackingConsumer
    websocket_urlpatterns += [
        re_path(r"ws/transport/route/(?P<route_id>\\d+)/$", RouteTrackingConsumer.as_asgi()),
    ]

Authorization note: this skeleton checks that the connecting user is a parent of a student
assigned to the route, or staff. Replace `_user_can_view_route` with your project's actual
permission check (e.g. querying StudentTransportAssignment via the parent's linked students).
"""
import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class RouteTrackingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.route_id = self.scope["url_route"]["kwargs"]["route_id"]
        self.group_name = f"route_{self.route_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated or not await self._user_can_view_route(user, self.route_id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def location_update(self, event):
        """Handler name must match the `type` key used in group_send (tasks.broadcast_location)."""
        await self.send(text_data=json.dumps(event))

    async def _user_can_view_route(self, user, route_id):
        # ASSUMPTION — replace with a real permission check against
        # StudentTransportAssignment / Parent-Student linkage, or staff role.
        return True


import json
from channels.generic.websocket import AsyncWebsocketConsumer

class VehicleTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.vehicle_id = self.scope['url_route']['kwargs']['vehicle_id']
        self.group_name = f'vehicle_{self.vehicle_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def location_update(self, event):
        await self.send(text_data=json.dumps(event['data']))
        
class FleetDashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tenant_id = self.scope['url_route']['kwargs']['tenant_id']
        self.group_name = f'fleet_{self.tenant_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def location_update(self, event):
        await self.send(text_data=json.dumps(event['data']))