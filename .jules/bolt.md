## 2024-10-02 - Optimize string prefix checking with tuples
**Learning:** Python's string `.startswith()` and `.endswith()` methods accept a tuple of strings. This is implemented in C and avoids the overhead of generator expressions or multiple boolean chain evaluations, yielding up to a 10x performance improvement for prefix matching operations.
**Action:** Always prefer `val.startswith((prefix1, prefix2))` over `any(val.startswith(p) for p in [prefix1, prefix2])` or multiple `or` conditions in string checks.
