## 2024-06-09 - Faster Prefix and Suffix Matching
**Learning:** Using generator expressions like `any(string.startswith(p) for p in prefixes)` is significantly slower in Python than passing a tuple directly to `str.startswith(tuple_of_prefixes)`. The latter is implemented in C and runs roughly 10x faster for short strings and lists.
**Action:** Always prefer `str.startswith(tuple)` and `str.endswith(tuple)` over loop constructs or `any()` when checking multiple prefixes or suffixes.
