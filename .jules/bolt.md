## 2024-05-24 - Optimize string prefix and suffix checking
**Learning:** Python's C-optimized tuple matching `str.startswith(("a", "b"))` is roughly 10x faster than generator expressions like `any(str.startswith(p) for p in list_of_prefixes)`. This is a useful micro-optimization for hot paths involving string checks.
**Action:** Always use a static tuple of prefixes or suffixes for `startswith` and `endswith` instead of iterating over a list with `any()`.
