from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT app, name, applied FROM django_migrations
        WHERE app = 'transport'
        ORDER BY id;
    """)
    for row in cursor.fetchall():
        print(row)
