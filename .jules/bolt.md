## 2024-06-17 - Fast Prefix/Suffix Matching
**Learning:** Checking for multiple string prefixes or suffixes using generator expressions like `any(s.startswith(prefix) for prefix in [...])` or chained conditions (`s.startswith("a") or s.startswith("b")`) is significantly slower than passing a tuple directly to `startswith()`/`endswith()` (`s.startswith(("a", "b"))`), which is implemented in C and runs roughly 10x faster.
**Action:** Use static tuples with `startswith()` and `endswith()` for multi-prefix/suffix checks in performance-critical code paths.
