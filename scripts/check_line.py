"""Inspect a specific line in start.ps1."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").splitlines()
line = lines[248]
print(f"Full: {repr(line)}")
for i, ch in enumerate(line):
    print(f"  {i}: {repr(ch)}")
