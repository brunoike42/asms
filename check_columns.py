from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'transport_student_assignment'
        ORDER BY ordinal_position;
    """)
    for row in cursor.fetchall():
        print(row)
    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'transport_student_assignment';
    """)
    print("---indexes---")
    for row in cursor.fetchall():
        print(row)
