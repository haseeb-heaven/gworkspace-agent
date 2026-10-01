## 2024-05-13 - Python startswith Optimizations
**Learning:** Checking string prefixes in Python using generator expressions (`any(val.startswith(p) for p in iterable)`) or long boolean `or` chains of `.startswith()` is significantly slower (up to 10x slower) than using C-optimized tuple matching `val.startswith((prefix1, prefix2, ...))`.
**Action:** Replace `any(...)` and long boolean chains for `startswith` checking with static literal tuples directly passed to `startswith` for immediate performance gains in string-heavy parsing code.
