## 2024-06-23 - Fast Prefix Checking
**Learning:** Using generator expressions like `any(val.startswith(p) for p in [...])` introduces Python-level iteration overhead. Passing a static tuple of prefixes to `str.startswith()` is implemented in C and evaluates significantly faster, which is critical in high-frequency validation paths like `_is_valid_drive_id`.
**Action:** Always use static tuples with `str.startswith()` and `str.endswith()` instead of generator expressions or chained `or` conditions when checking against multiple prefixes/suffixes.
