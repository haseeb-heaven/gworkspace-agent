## 2024-07-15 - Fast Multiple Prefix/Suffix Checking
**Learning:** Using generator expressions like `any(s.startswith(p) for p in prefixes)` or chained `or` conditions for prefix/suffix checking introduces significant overhead. Passing a static tuple directly to `str.startswith()` or `str.endswith()` is implemented in C and executes much faster.
**Action:** Always use tuples with `startswith()` and `endswith()` when checking multiple static prefixes or suffixes.
