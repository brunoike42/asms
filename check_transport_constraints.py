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
    print("=== Constraints: transport_vehicle ===")
    cursor.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'transport_vehicle'::regclass;
    """)
    for row in cursor.fetchall():
        print(" ", row)
    print()
    print("=== Row counts: vehicle_location_ping tables ===")
    cursor.execute("SELECT COUNT(*) FROM transport_vehicle_location_ping;")
    print("  transport_vehicle_location_ping:", cursor.fetchone()[0])
    print()
    print("=== Columns: transport_vehicle_location_ping ===")
    cursor.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'transport_vehicle_location_ping'
        ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(" ", row)
    print()
    print("=== Row counts: route, stop, vehicle, student_assignment ===")
    for t in ["transport_route", "transport_stop", "transport_vehicle", "transport_student_assignment"]:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        print(f"  {t}:", cursor.fetchone()[0])
