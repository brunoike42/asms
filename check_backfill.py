from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM transport_student_assignment")
    print("total rows:", cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM transport_student_assignment WHERE stop_id IS NOT NULL")
    print("rows with legacy stop_id set:", cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM transport_student_assignment WHERE stop_id IS NOT NULL AND (pickup_stop_id IS NULL OR dropoff_stop_id IS NULL)")
    print("rows needing backfill:", cursor.fetchone()[0])
