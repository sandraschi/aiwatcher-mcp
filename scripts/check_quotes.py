"""Find odd double-quote counts per line in start.ps1."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").split("\n")

for i, line in enumerate(lines):
    dq = line.count('"')
    if dq % 2 != 0 and not line.strip().startswith("#"):
        print(f"Line {i + 1}: odd quotes ({dq}): {line[:80]}")
