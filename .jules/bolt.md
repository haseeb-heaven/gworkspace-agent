## 2024-10-25 - C-Optimized Prefix Matching
**Learning:** Python's `str.startswith()` and `str.endswith()` natively support tuple arguments, checking multiple prefixes simultaneously via C-optimized code. This is significantly faster than generator expressions like `any(val.startswith(p) for p in prefixes)`.
**Action:** Always replace `any(val.startswith(p) for p in iter)` with `val.startswith(tuple_of_prefixes)`. Ensure the tuple is defined statically or converted exactly once.
