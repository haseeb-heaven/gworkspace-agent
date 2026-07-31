## 2024-07-24 - Optimize multiple string prefix/suffix checking
**Learning:** Using generator expressions like `any(val.startswith(p) for p in prefixes)` introduces overhead. `str.startswith()` and `str.endswith()` in Python natively accept a tuple of strings, which is executed much faster because the looping is implemented in C.
**Action:** Replace `any(...)` with `.startswith(tuple)` or `.endswith(tuple)` using a static tuple of prefixes/suffixes, particularly in frequently called validation methods.
