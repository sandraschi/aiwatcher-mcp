"""Find backtick line continuations."""
p = __file__.replace('scripts\\backtick_check.py', 'start.ps1')
c = open(p, encoding='utf-8').read()
lines = c.split('\n')
for i, l in enumerate(lines):
    if l.endswith('`') and not l.strip().startswith('#'):
        print(f'Line {i+1}: {l[:80]}')
