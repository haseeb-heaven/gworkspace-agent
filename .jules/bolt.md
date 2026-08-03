## 2025-05-18 - Optimized string suffix/prefix checks
**Learning:** Generator expressions inside `any()` for string checks (e.g. `any(s.endswith(x) for x in lst)`) introduce unnecessary Python overhead and execute significantly slower (~10x) than simply passing a static tuple directly to `str.startswith()` and `str.endswith()`.
**Action:** Use literal tuples with `str.startswith()` and `str.endswith()` instead of iterating over a list with `any()` whenever checking multiple string prefixes/suffixes.
