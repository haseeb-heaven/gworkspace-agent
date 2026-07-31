## 2024-05-24 - String prefix/suffix checking optimization
**Learning:** Checking for multiple string prefixes or suffixes in Python using generator expressions (e.g. `any(val.startswith(p) for p in prefixes)`) is significantly slower than passing a static tuple to `.startswith()` or `.endswith()` (e.g. `val.startswith(tuple_of_prefixes)`). The tuple passing is implemented in C and runs roughly ~10x faster.
**Action:** Always prefer using a literal tuple with `.startswith()` or `.endswith()` when checking for multiple prefixes or suffixes, rather than generator expressions.
