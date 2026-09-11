from django.db import connection
with connection.cursor() as cursor:
    print("=== Constraints: transport_route ===")
    cursor.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'transport_route'::regclass;
    """)
    for row in cursor.fetchall():
        print(" ", row)
    print()
    print("=== Constraints: transport_stop ===")
    cursor.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'transport_stop'::regclass;
    """)
    for row in cursor.fetchall():
        print(" ", row)
    print()
    print("=== Columns: transport_route ===")
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'transport_route' ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(" ", row[0])
    print()
    print("=== Columns: transport_vehicle ===")
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'transport_vehicle' ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(" ", row[0])
    print()
    print("=== Columns: transport_stop ===")
    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'transport_stop' ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(" ", row[0])
    print()
    print("=== All transport* tables now in DB ===")
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE 'transport%'
        ORDER BY table_name;
    """)
    for row in cursor.fetchall():
        print(" ", row[0])
