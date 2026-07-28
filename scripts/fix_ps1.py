"""Fix single quotes in minimal start.ps1."""

p = r"D:\Dev\repos\aiwatcher-mcp\start.ps1"
c = open(p, encoding="utf-8").read()
c = c.replace(
    '"Install it first: just service-install"', "'Install it first: just service-install'"
)
c = c.replace('"Service restarted"', "'Service restarted'")
open(p, "w", encoding="utf-8").write(c)
print("Done")
