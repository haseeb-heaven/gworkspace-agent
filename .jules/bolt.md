## 2024-05-18 - [Optimize startswith]
**Learning:** Python string prefix/suffix checking with generator expressions like `any(val.startswith(p) for p in iter)` or long boolean `or` chains of `startswith()` calls is significantly slower than using C-optimized tuple matching like `val.startswith(tuple_of_prefixes)`.
**Action:** Replace generator expressions and long boolean chains of `startswith` checks with `startswith(tuple)`.
