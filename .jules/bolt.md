## 2024-05-24 - Python String Prefix/Suffix Optimization
**Learning:** Checking for multiple prefixes/suffixes using a list and `any(s.endswith(x) for x in list)` adds Python-level iteration overhead. Passing a static tuple directly to `str.startswith()` or `str.endswith()` leverages C-level implementation, making it significantly faster.
**Action:** Always use static tuples with `startswith`/`endswith` for multiple substring matching instead of generator expressions or chained `or` conditions, provided the tuple is a static literal.
