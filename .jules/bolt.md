## 2024-05-15 - [Python Prefix/Suffix Checking]
**Learning:** Checking for multiple prefixes/suffixes using a generator expression inside `any()` (e.g., `any(s.startswith(p) for p in prefixes)`) is significantly slower than passing a literal tuple directly to `str.startswith(tuple)` or `str.endswith(tuple)` because the tuple method evaluates the string in optimized C code.
**Action:** Always prefer passing a static literal tuple to `str.startswith()` and `str.endswith()` over using generator expressions for prefix and suffix checks.
