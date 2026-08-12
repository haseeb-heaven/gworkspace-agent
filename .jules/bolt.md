## 2024-08-12 - Optimize String Prefix Checking
**Learning:** Checking for multiple string prefixes using a generator expression like `any(s.startswith(p) for p in [...])` introduces unnecessary Python interpreter overhead. Using `s.startswith((...))` with a static tuple literal is implemented in C and is significantly faster (~10x speedup).
**Action:** Always prefer `str.startswith(tuple)` or `str.endswith(tuple)` over generator expressions or chained `or` conditions when checking multiple static string prefixes or suffixes to improve execution speed.
