from django.apps import apps
print("\n=== MODEL MANAGER AUDIT ===\n")
for m in apps.get_models():
    tenant_field = any(f.name == "tenant" for f in m._meta.fields)
    print(
        "{} | objects={} | tenant_field={} | abstract={}".format(
            m._meta.label,
            type(m.objects).__name__,
            "YES" if tenant_field else "NO",
            m._meta.abstract,
        )
    )
