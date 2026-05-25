## 2024-05-18 - [Optimize Prefix Checking]
**Learning:** Using `any()` with list comprehensions for checking string prefixes is significantly slower than passing a tuple directly to `str.startswith()` because the tuple approach is implemented in C.
**Action:** Always prefer `str.startswith((tuple_of_prefixes))` over `any(s.startswith(p) for p in [...])` or chained `or` conditions for multiple prefix checks to improve string matching performance.
