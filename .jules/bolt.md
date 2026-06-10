## 2024-06-10 - String Matching Optimization
**Learning:** Python's `str.startswith()` and `str.endswith()` methods accept tuples of strings, which evaluates in C and is significantly faster than using generator expressions like `any(s.startswith(p) for p in prefixes)` or chaining multiple `startswith` checks with `or`.
**Action:** Always prefer passing tuples to `startswith` and `endswith` for multiple prefix/suffix checks in hot paths.
