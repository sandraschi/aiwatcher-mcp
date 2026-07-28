"""One-off quote fixer for start.ps1."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
content = p.read_text(encoding="utf-8")
content = content.replace(
    '"Install it first: just service-install"', "'Install it first: just service-install'"
)
content = content.replace('"Service restarted"', "'Service restarted'")
p.write_text(content, encoding="utf-8")
print("Done")
