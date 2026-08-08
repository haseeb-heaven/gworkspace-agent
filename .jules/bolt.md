## 2024-05-24 - Efficient Prefix/Suffix Checking
**Learning:** Checking for multiple string prefixes/suffixes using a generator expression like `any(s.startswith(p) for p in prefixes)` is slower than passing a static tuple directly to `str.startswith()` or `str.endswith()`. Passing a tuple executes in C and is significantly faster.
**Action:** Replace `any(...)` generator expressions for prefix/suffix checks with `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)` using static literal tuples to maximize performance.
