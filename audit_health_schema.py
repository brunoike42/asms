from django.apps import apps
from django.db import connection
app_label = "health"  # change if your app is named differently
with connection.cursor() as cursor:
    print("=== django_migrations entries for app=" + app_label + " ===")
    cursor.execute("""
        SELECT id, app, name, applied FROM django_migrations
        WHERE app = %s
        ORDER BY id;
    """, [app_label])
    for row in cursor.fetchall():
        print(" ", row)
    print()
    print("=== Live tables matching this app's models ===")
    try:
        models_by_table = {m._meta.db_table: m for m in apps.get_app_config(app_label).get_models()}
    except LookupError:
        print(f"  App '{app_label}' not found — check the label (e.g. apps.health, health, nurse, etc.)")
        models_by_table = {}
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    live_tables = {row[0] for row in cursor.fetchall()}
    print()
    print("=== Model tables missing from DB entirely ===")
    for table, model in sorted(models_by_table.items()):
        if table not in live_tables:
            print(" ", table, "->", model.__name__)
    print()
    print("=== Column-level diff (tables present on both sides) ===")
    for table, model in sorted(models_by_table.items()):
        if table not in live_tables:
            continue
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
        else:
            print(f"--- {table} ({model.__name__}): OK, matches ---")
