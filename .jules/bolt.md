## 2024-06-29 - Optimize multiple startswith string checking with Tuple
**Learning:** Python's `str.startswith` method accepts a tuple of strings. It is implemented in C and avoids the overhead of executing generator comprehensions with `any(...)`.
**Action:** Always prefer `startswith((prefix1, prefix2))` over `any(s.startswith(p) for p in [...])`.
