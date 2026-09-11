from django.apps import apps
from django.db import connection
app_label = "transport"
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name LIKE %s
        ORDER BY table_name;
    """, ["transport_%"])
    live_tables = {row[0] for row in cursor.fetchall()}
print("=== Live tables (transport_*) ===")
for t in sorted(live_tables):
    print(" ", t)
models_by_table = {m._meta.db_table: m for m in apps.get_app_config(app_label).get_models()}
print()
print("=== Model tables missing from DB entirely ===")
for table, model in sorted(models_by_table.items()):
    if table not in live_tables:
        print(" ", table, "->", model.__name__)
print()
print("=== DB tables with no matching model ===")
for table in sorted(live_tables - set(models_by_table)):
    print(" ", table)
print()
print("=== Column-level diff (tables present on both sides) ===")
for table, model in sorted(models_by_table.items()):
    if table not in live_tables:
        continue
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
        """, [table])
        live_cols = {row[0] for row in cursor.fetchall()}
    model_cols = set()
    for f in model._meta.get_fields():
        col = getattr(f, "column", None)
        if col:
            model_cols.add(col)
    missing = model_cols - live_cols
    extra = live_cols - model_cols
    if missing or extra:
        print(f"--- {table} ({model.__name__}) ---")
        if missing:
            print("    model expects, DB missing:", sorted(missing))
        if extra:
            print("    DB has, model has no field for:", sorted(extra))
