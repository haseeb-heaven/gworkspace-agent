## 2024-06-06 - Optimize string prefix/suffix checks
**Learning:** Using `any(s.startswith(prefix) for prefix in prefixes)` with a generator expression is significantly slower than passing a tuple directly to `s.startswith(prefixes_tuple)`. Passing a tuple is implemented in C and executes much faster.
**Action:** Always prefer using a tuple with `str.startswith()` and `str.endswith()` over a generator expression for performance-critical prefix/suffix matching.
