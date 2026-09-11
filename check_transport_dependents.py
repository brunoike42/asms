from django.db import connection
with connection.cursor() as cursor:
    print("=== All transport* tables currently in DB ===")
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE 'transport%'
        ORDER BY table_name;
    """)
    for row in cursor.fetchall():
        print(" ", row[0])
    print()
    print("=== Foreign keys FROM non-transport tables INTO transport* tables ===")
    cursor.execute("""
        SELECT
            tc.table_name AS referencing_table,
            kcu.column_name AS referencing_column,
            ccu.table_name AS referenced_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name LIKE 'transport%'
          AND tc.table_name NOT LIKE 'transport%';
    """)
    rows = cursor.fetchall()
    if not rows:
        print("  (none found)")
    for row in rows:
        print(" ", row)
    print()
    print("=== Row counts for any external referencing tables found ===")
    referencing_tables = sorted(set(r[0] for r in rows))
    for t in referencing_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        print(f"  {t}:", cursor.fetchone()[0])
    print()
    print("=== django_migrations entries for app=transport ===")
    cursor.execute("""
        SELECT id, app, name, applied FROM django_migrations
        WHERE app = 'transport'
        ORDER BY id;
    """)
    for row in cursor.fetchall():
        print(" ", row)
