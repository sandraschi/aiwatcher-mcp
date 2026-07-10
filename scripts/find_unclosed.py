"""Find unclosed double-quoted strings in a PS1 file."""
import pathlib

p = pathlib.Path(__file__).resolve().parent.parent / "start.ps1"
lines = p.read_text(encoding="utf-8").split("\n")

# Track string state
in_string = False
for i, l in enumerate(lines):
    stripped = l.strip()
    if stripped.startswith("#"):
        continue  # skip comments

    # Count unescaped double quotes
    dq_count = 0
    j = 0
    while j < len(l):
        if l[j] == '"' and (j == 0 or l[j-1] != '`'):
            dq_count += 1
        j += 1

    if dq_count % 2 != 0:
        print(f"Line {i+1}: odd double quotes ({dq_count}): {l[:80]}")

print("Done")
