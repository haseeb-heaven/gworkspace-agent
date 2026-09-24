## 2024-09-24 - [Optimize prefix matching]
**Learning:** Generator expressions with `any(val.startswith(p) for p in iter)` are significantly slower than C-optimized tuple matching `val.startswith(tuple_of_prefixes)`.
**Action:** Replace generator expressions testing for multiple prefixes with tuple arguments passed directly to `startswith()`.
