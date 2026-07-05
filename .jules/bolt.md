## 2024-07-05 - Optimize string prefix lookups
**Learning:** Using generator expressions like `any(s.startswith(p) for p in [a,b])` is significantly slower (up to 8x) than passing a static tuple directly to `s.startswith((a,b))`, because the tuple lookup is implemented in C and executes much faster natively.
**Action:** Always prefer `startswith(tuple)` or `endswith(tuple)` over chained `or` or generator expressions when checking for multiple prefixes/suffixes in Python strings.
