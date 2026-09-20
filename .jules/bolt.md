## 2025-01-28 - Optimize string prefix/suffix checking
**Learning:** Replacing generator expressions like `any(val.startswith(p) for p in iter)` with C-optimized tuple matching like `val.startswith(tuple_of_prefixes)` provides an ~8-9x speedup in Python. The tuple should be a static literal to avoid dynamic conversion overhead.
**Action:** Always use `str.startswith(tuple)` or `str.endswith(tuple)` instead of `any()` with a generator expression when checking against multiple prefixes/suffixes.
