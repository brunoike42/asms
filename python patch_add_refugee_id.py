# patch_add_refugee_id.py
import pathlib

path = pathlib.Path("apps/students/models.py")
text = path.read_text(encoding="utf-8")

anchor = "    is_refugee           = models.BooleanField(default=False)\n"

if anchor not in text:
    raise SystemExit("Anchor not found — file may have changed since recon. Aborting, no changes made.")

if text.count(anchor) != 1:
    raise SystemExit(f"Anchor found {text.count(anchor)} times — expected exactly 1. Aborting for safety.")

insert = (
    '    refugee_or_pass_id    = models.CharField(\n'
    '        max_length=50, blank=True, default="",\n'
    '        verbose_name="Refugee ID / student pass number",\n'
    '        help_text="Refugee ID number or special student pass number, for refugee/asylum students.",\n'
    '    )\n'
)

patched = text.replace(anchor, anchor + insert, 1)
path.write_text(patched, encoding="utf-8", newline="\n")
print("Patched apps/students/models.py — refugee_or_pass_id inserted after is_refugee.")