## 2024-11-21 - Optimize string prefix/suffix checks
**Learning:** Python string methods `startswith` and `endswith` accept a tuple directly, which is processed via C-optimized routines. Using a generator expression `any(val.startswith(p) for p in [..])` introduces significant overhead (up to ~10x slower).
**Action:** Always use a static tuple for multiple prefix/suffix checks (e.g., `val.startswith(('a', 'b'))`) instead of generator expressions.
