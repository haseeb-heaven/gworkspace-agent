## 2024-11-20 - Tuple fast path is faster than generator any()
**Learning:** Using a generator expression like `any(val.startswith(p) for p in iter)` introduces overhead compared to native C-optimized tuple matching like `val.startswith(tuple_of_prefixes)`.
**Action:** Always prefer `startswith(tuple)` or `endswith(tuple)` over generator loop checks for multiple prefixes/suffixes to improve runtime performance.
