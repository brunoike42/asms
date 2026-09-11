from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'transport_route'
        ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(row)
    print("---indexes---")
    cursor.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'transport_route';")
    for row in cursor.fetchall():
        print(row)
