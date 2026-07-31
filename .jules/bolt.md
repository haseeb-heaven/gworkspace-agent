## 2025-02-12 - Performance Optimizations
**Learning:** Checking for prefixes/suffixes with `tuple` is faster than generator expressions or chained ORs.
**Action:** When finding multiple string prefixes/suffixes, use `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)`.
