"""Find odd single-quote counts per line in start.ps1."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").split("\n")
for i, line in enumerate(lines):
    sq_in_line = line.count("'")
    if sq_in_line % 2 != 0:
        print(f"Line {i + 1}: odd single quotes ({sq_in_line}): {line[:80]}")
