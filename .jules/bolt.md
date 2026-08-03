## 2025-06-11 - Optimize string prefix/suffix checking
**Learning:** Checking for multiple string prefixes or suffixes in Python using `any(val.startswith(p) for p in [...])` or `any(val.endswith(p) for p in [...])` is significantly slower than using `val.startswith(tuple_of_prefixes)` or `val.endswith(tuple_of_suffixes)`. The tuple version is implemented in C and evaluates 5-8x faster.
**Action:** When acting as Bolt, apply this optimization to hot paths like path resolution and validation engines where frequent string prefix/suffix checks occur.
