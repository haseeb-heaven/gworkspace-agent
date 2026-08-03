## 2025-07-03 - [Optimize string prefix checks]
**Learning:** Using a generator expression with `any(...)` for string prefix checks (`any(s.startswith(p) for p in list)`) is roughly 10x slower than passing a static tuple directly to `startswith` (`s.startswith((p1, p2, ...))`) because the latter is implemented entirely in C.
**Action:** Always prefer `str.startswith(tuple_of_prefixes)` and `str.endswith(tuple_of_suffixes)` with literal tuples over generator expressions or chained `or` conditions for multi-prefix/suffix checks.
