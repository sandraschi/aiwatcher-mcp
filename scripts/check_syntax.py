"""Check PS script brace and quote balance."""
p = __file__.replace('scripts\\check_syntax.py', 'start.ps1')
c = open(p, encoding='utf-8').read()
lines = c.split('\n')
for i, l in enumerate(lines):
    sq_in_line = l.count("'")
    if sq_in_line % 2 != 0:
        print(f'  Unbalanced sq at line {i+1}: {l[:100]}')
