## 2024-07-18 - [Python Native string methods vs Generator expressions]
**Learning:** Using generator expressions with `any()` (e.g. `any(s.startswith(prefix) for prefix in prefixes)`) is significantly slower than passing a tuple directly to `str.startswith()` or `str.endswith()` because the tuple approach is implemented natively in C.
**Action:** Always prefer `str.startswith((...))` or `str.endswith((...))` with a static tuple over list comprehensions or generators when checking for multiple prefixes/suffixes.
