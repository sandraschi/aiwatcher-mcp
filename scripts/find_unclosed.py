"""Find unclosed double-quoted strings in a PS1 file."""

import pathlib

p = pathlib.Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").split("\n")

# Track string state
in_string = False
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("#"):
        continue  # skip comments

    # Count unescaped double quotes
    dq_count = 0
    j = 0
    while j < len(line):
        if line[j] == '"' and (j == 0 or line[j - 1] != "`"):
            dq_count += 1
        j += 1

    if dq_count % 2 != 0:
        print(f"Line {i + 1}: odd double quotes ({dq_count}): {line[:80]}")

print("Done")
