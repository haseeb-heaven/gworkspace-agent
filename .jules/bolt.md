## 2024-05-24 - [Optimize string prefix checking]
**Learning:** In Python, checking string prefixes using multiple `.startswith()` calls separated by `or`, or using an `any()` generator expression with `.startswith()`, is less performant due to the overhead of multiple method calls or generator creation.
**Action:** Pass a tuple of prefixes to a single `.startswith()` call (e.g. `val.startswith(("prefix1", "prefix2"))`). Tuple matching is implemented in C and can be up to 10x faster.
