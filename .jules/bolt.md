## 2025-01-20 - Optimize string suffix matching
**Learning:** Python's C-level tuple matching `str.endswith(("a", "b"))` is >10x faster than generator expressions `any(str.endswith(s) for s in list)`.
**Action:** Always convert static suffix lists to tuples and pass them directly to `endswith()` instead of using `any()`.
