## 2024-06-22 - Optimize prefix matching with tuples
**Learning:** Checking for multiple string prefixes using a generator expression like `any(s.startswith(p) for p in ...)` or chained `or` conditions is inefficient. Using `str.startswith(tuple_of_prefixes)` evaluates significantly faster as the loop is implemented in C.
**Action:** Whenever checking multiple prefixes statically, use a tuple with `startswith` directly.
