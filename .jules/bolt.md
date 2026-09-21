## 2024-09-21 - C-optimized Tuple Prefix Matching
**Learning:** Checking string prefixes using long `or` chains (`a.startswith(x) or a.startswith(y)`) or generator expressions (`any(a.startswith(x) for x in list)`) has significant Python-level overhead.
**Action:** Use Python's built-in tuple support in `.startswith()` (e.g., `a.startswith(("x", "y"))`) which delegates the matching to the highly optimized C backend.
