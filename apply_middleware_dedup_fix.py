import shutil
from pathlib import Path

path = Path("apps/core/middleware.py")
backup = Path("apps/core/middleware.py.bak")

text = path.read_text(encoding="utf-8-sig")

marker = "class TenantMiddleware:"
count = text.count(marker)
if count != 2:
    raise SystemExit(f"SAFETY CHECK FAILED: expected exactly 2 occurrences of 'class TenantMiddleware:', found {count}. Aborting, no changes made.")

first_idx = text.find(marker)
second_idx = text.find(marker, first_idx + 1)

end_anchor = "return Tenant.objects.filter(is_active=True).first()"
if text.count(end_anchor) != 1:
    raise SystemExit(f"SAFETY CHECK FAILED: expected exactly 1 occurrence of end_anchor, found {text.count(end_anchor)}. Aborting.")

end_idx = text.find(end_anchor)
if not (first_idx < end_idx < second_idx):
    raise SystemExit("SAFETY CHECK FAILED: anchors are not in the expected order. Aborting, no changes made.")

between = text[end_idx + len(end_anchor):second_idx]
if len(between) > 300:
    raise SystemExit(
        f"SAFETY CHECK FAILED: unexpected amount of content ({len(between)} chars) between the "
        f"end of the first class and the second 'class TenantMiddleware:'. Aborting, no changes made."
    )

new_text = text[:end_idx + len(end_anchor)].rstrip("\n") + "\n"

# Sanity check the result
if new_text.count(marker) != 1:
    raise SystemExit("POST-CHECK FAILED: result does not contain exactly 1 class definition. Aborting write.")
if new_text.count("def _resolve_tenant") != 1:
    raise SystemExit("POST-CHECK FAILED: result does not contain exactly 1 _resolve_tenant definition. Aborting write.")
if new_text.count("def _dev_tenant") != 1:
    raise SystemExit("POST-CHECK FAILED: result does not contain exactly 1 _dev_tenant definition. Aborting write.")

shutil.copy(path, backup)
path.write_text(new_text, encoding="utf-8", newline="\n")

print("Patch applied successfully.")
print(f"Backup saved to: {backup}")
print(f"Removed {len(text) - len(new_text)} characters (stray duplicate class).")