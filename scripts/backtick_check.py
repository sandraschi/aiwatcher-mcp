"""Find backtick line continuations."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").split("\n")
for i, line in enumerate(lines):
    if line.endswith("`") and not line.strip().startswith("#"):
        print(f"Line {i + 1}: {line[:80]}")
