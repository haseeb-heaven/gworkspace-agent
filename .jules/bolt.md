## 2025-02-18 - Optimize multiple string prefix/suffix matching
**Learning:** Checking for multiple string prefixes/suffixes by iterating over a list/generator using `any(s.startswith(p) for p in prefixes)` is significantly slower in Python than `s.startswith(tuple_of_prefixes)`. `startswith` and `endswith` are implemented in C and accept tuples natively.
**Action:** When making string prefix/suffix checks against multiple possible patterns, ensure the patterns are passed as a tuple directly to `str.startswith()` or `str.endswith()` instead of using `any()` with a generator expression.
