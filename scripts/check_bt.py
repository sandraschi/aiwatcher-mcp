"""Check if line 188 has a proper backtick continuation."""

p = __file__.replace("scripts\\check_bt.py", "start.ps1")
lines = open(p, encoding="utf-8").readlines()
l = lines[187]  # line 188 (0-indexed)
print(f"Line 188 ends with: {repr(l[-20:])}")
has_bt = chr(96) in l  # backtick
print(f"Backtick present: {has_bt}")
print(f"Last non-space char is backtick: {l.rstrip().endswith(chr(96))}")
