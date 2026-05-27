## 2024-05-27 - Tuple-based startswith optimization
**Learning:** Using `str.startswith()` with a tuple of strings is implemented in C and executes significantly faster than using an `any()` generator expression with `startswith()` on a list or set of strings.
**Action:** When checking for multiple string prefixes in Python, always prefer using `str.startswith(tuple_of_prefixes)` over `any(val.startswith(prefix) for prefix in list_of_prefixes)`.
