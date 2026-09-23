## 2024-09-23 - Optimize String Prefix Checks
**Learning:** Using `generator expressions` with `any()` for string prefix checks (`any(val.startswith(p) for p in iter)`) is ~10x slower than using Python's native C-optimized tuple matching (`val.startswith(tuple)`). Similar performance gains apply to replacing long chains of boolean `or` evaluations of `startswith()`.
**Action:** Use tuple matching `val.startswith(("prefix1", "prefix2"))` instead of generator expressions or long boolean chains for performance improvements when dealing with string prefixes.
