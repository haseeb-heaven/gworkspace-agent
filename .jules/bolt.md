## 2024-06-15 - Tuple Startswith Evaluation
**Learning:** Using `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)` is implemented in C and evaluates significantly faster than generator expressions like `any(...)` or a for-loop with individual `endswith()` calls.
**Action:** Always prefer tuples for prefix/suffix matching when checking multiple string patterns.
