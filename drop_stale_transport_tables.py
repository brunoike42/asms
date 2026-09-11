from django.db import connection
tables = [
    "transport_route",
    "transport_stop",
    "transport_student_assignment",
    "transport_vehicle",
    "transport_vehicle_location_ping",
]
with connection.cursor() as cursor:
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
        print(f"Dropped {t}")
