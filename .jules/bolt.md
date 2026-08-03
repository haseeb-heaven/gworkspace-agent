## 2024-07-19 - Fast string prefix/suffix checking
**Learning:** Using `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)` is implemented in C and executes up to 10x faster than using generator expressions like `any(...)` or chained `or` conditions in Python.
**Action:** Always prefer passing a static literal tuple to `.startswith()` or `.endswith()` when checking for multiple prefixes/suffixes to maximize performance.
