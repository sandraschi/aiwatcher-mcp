"""Check backtick on a specific line in start.ps1."""

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").splitlines()
line = lines[187]  # line 188 (0-indexed)
print(f"Line 188 ends with: {repr(line[-20:])}")
has_bt = chr(96) in line  # backtick
print(f"Has backtick: {has_bt}")
