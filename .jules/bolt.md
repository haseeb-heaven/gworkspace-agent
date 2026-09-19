## YYYY-MM-DD - Tuple startswith optimization
**Learning:** Using `s.startswith(tuple_of_prefixes)` is vastly faster (up to ~10x) than `any(s.startswith(prefix) for prefix in [...])` or chaining `s.startswith("a") or s.startswith("b")` because it pushes the loop down to C level instead of creating a generator and calling Python functions repeatedly.
**Action:** Always prefer passing a static tuple of prefixes to `startswith()` instead of manual loops or generator expressions for string prefix matching.
