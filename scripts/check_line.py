"""Check line 249 for hidden chars."""
p = __file__.replace('scripts\\check_line.py', 'start.ps1')
lines = open(p, encoding='utf-8').readlines()
l = lines[248]
print(f'Full: {repr(l)}')
for i, c in enumerate(l):
    if ord(c) > 127 or ord(c) < 32:
        print(f'  char {i}: U+{ord(c):04X} ({repr(c)})')
