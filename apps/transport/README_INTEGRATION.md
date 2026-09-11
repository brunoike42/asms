# Integrating the Transport Module Into the Existing ASMS Codebase

This app was built standalone since I don't have your actual Phase 1–3 code in front of me. It follows
the architectural rules already established in the base spec (tenant isolation, Celery event pattern,
Channels for real-time, Appendix E API conventions), so integration should be mechanical. Steps:

## 1. Drop in the app
Copy the `transport/` directory into your project root (next to your other apps like `students/`, `finance/`).

## 2. Fix the three assumed imports
Search the app for `ASSUMPTION` comments. There are three:

| File | Assumed import | What to change it to |
|---|---|---|
| `transport/models.py` | `from core.models import TenantAwareModel` | Your actual tenant base model location |
| `transport/models.py` | `"staff.Staff"`, `"students.Student"` FK strings | Your actual app labels for staff/students |
| `transport/tasks.py` | `from notifications.sms import send_sms` | Your actual Africa's Talking wrapper location |

If you don't yet have a `TenantAwareModel`, a minimal version is included as a comment at the top of
`models.py`.

## 3. Register the app
```python
# settings.py
INSTALLED_APPS += ["transport"]
```

## 4. Run migrations
```bash
python manage.py makemigrations transport
python manage.py migrate
```

## 5. Mount the API routes
```python
# project urls.py
path("api/v1/transport/", include("transport.urls")),
```

## 6. Wire the WebSocket route (Channels)
```python
# asgi.py
from transport.consumers import RouteTrackingConsumer
websocket_urlpatterns += [
    re_path(r"ws/transport/route/(?P<route_id>\d+)/$", RouteTrackingConsumer.as_asgi()),
]
```
Also replace `RouteTrackingConsumer._user_can_view_route` with a real permission check
(parent of an assigned student, or staff with transport visibility).

## 7. Add the Celery Beat schedule entry
```python
# celery.py or settings.py CELERY_BEAT_SCHEDULE
"transport-daily-document-expiry-check": {
    "task": "transport.tasks.daily_document_expiry_check",
    "schedule": crontab(hour=6, minute=0),
},
```

## 8. Front-end hookups
- **Parent portal live map:** call `GET /api/v1/transport/students/{id}/status/` for the current
  vehicle location + ETA, then subscribe to `ws/transport/route/{route_id}/` for live updates on
  the same Google Maps Platform map already used elsewhere in the stack (Section 17).
- **Driver app:** `transport/templates/transport/driver_app.html` is a reference implementation of
  the offline-queue-and-sync pattern — treat it as a starting point for the real driver PWA screen,
  not a finished UI. Inject `ASMS_TRIP_ID` and `ASMS_TOKEN` via your template context.
- **Printable Transport Card (Document #13, Section 12):** unchanged — pull `route`, `pickup_stop`,
  `assigned` vehicle registration from `StudentTransportAssignment`.

## 9. What's intentionally not built yet (see spec §2)
Driver-behaviour scoring, AI-predicted delays, and fuel reconciliation are deferred — per Appendix
B's rule that intelligence features wait until there's enough trip-history data to train on. The
`VehicleLocationPing` and `TripLog` tables are already shaped so that data accumulates from day one
and can feed the ACI Engine (Module 5.17) once volume justifies it.
