## 2024-05-23 - Optimize string prefix and suffix checks
**Learning:** Python's `str.startswith()` and `str.endswith()` methods natively support tuples of strings, which is implemented in C and runs significantly faster than generator expressions like `any(s.startswith(x) for x in list)` or chained `or` conditions.
**Action:** Replace generator expressions and chained `or` checks with a static literal tuple passed directly to `startswith()` or `endswith()` for improved performance.
