from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM transport_route;")
    print("transport_route rows:", cursor.fetchone()[0])
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables WHERE table_name = 'transport_driver'
        );
    """)
    print("transport_driver table exists:", cursor.fetchone()[0])
