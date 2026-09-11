import shutil
from pathlib import Path

path = Path("apps/transport/views.py")
backup = Path("apps/transport/views.py.bak")

text = path.read_text(encoding="utf-8-sig")

anchor_class = "class TenantCreateMixin:"
anchor_insert = "def envelope(data, meta=None):"

idx_class = text.find(anchor_class)
if idx_class == -1:
    raise SystemExit("ANCHOR NOT FOUND: 'class TenantCreateMixin:' not found. Aborting, no changes made.")

if text.count(anchor_insert) != 1:
    raise SystemExit(f"ANCHOR NOT UNIQUE: 'def envelope(...)' found {text.count(anchor_insert)} times, expected 1. Aborting.")

tail_after_mixin_header = text[idx_class:]
lines_after = tail_after_mixin_header.split("\n")
if len(lines_after) > 10:
    raise SystemExit(
        f"SAFETY CHECK FAILED: expected TenantCreateMixin block near EOF to be ~5-6 lines, "
        f"found {len(lines_after)}. File structure differs from what was reviewed. Aborting, no changes made."
    )

mixin_block = text[idx_class:].rstrip("\n")
text_without_mixin = text[:idx_class].rstrip("\n") + "\n"

new_text = text_without_mixin.replace(
    anchor_insert,
    mixin_block + "\n\n\n" + anchor_insert,
    1,
)

shutil.copy(path, backup)
path.write_text(new_text, encoding="utf-8", newline="\n")

print("Patch applied successfully.")
print(f"Backup saved to: {backup}")
print()
print("--- Relocated block ---")
print(mixin_block)