## 2024-08-22 - Optimize String Prefix Checks
**Learning:** Using generator expressions like `any(val.startswith(p) for p in iter)` introduces overhead compared to C-optimized tuple matching (`val.startswith(tuple_of_prefixes)`). The tuple matching is significantly faster (~7x in microbenchmarks).
**Action:** Always use a static literal tuple with `startswith` or `endswith` for prefix/suffix checking instead of generator expressions.
