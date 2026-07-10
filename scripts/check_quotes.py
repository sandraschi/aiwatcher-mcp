"""Analyze quote balance in start.ps1."""
p = r'D:\Dev\repos\aiwatcher-mcp\start.ps1'
c = open(p, encoding='utf-8').read()
lines = c.split('\n')

for i, l in enumerate(lines):
    dq = l.count('"')
    if dq % 2 != 0 and not l.strip().startswith('#'):
        print(f'Line {i+1}: ODD double quotes ({dq}): {l[:80]}')
