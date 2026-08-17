## 2024-08-17 - [Tuple vs Generator Expression in startswith]
**Learning:** Generator expressions in `any()` for checking string prefixes are significantly slower (~10x for negative cases, ~7.5x for positive cases) compared to passing a tuple directly to `str.startswith()`. The tuple approach leverages Python's internal C optimization.
**Action:** Replace `any(val.startswith(p) for p in iter)` with `val.startswith((tuple_of_prefixes))` wherever performance is a priority.
