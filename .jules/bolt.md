## 2024-08-21 - C-optimized Tuple Matching for String Prefix/Suffix Checking
**Learning:** Python's generator expressions inside `any()` for checking string prefixes and suffixes (e.g., `any(s.startswith(p) for p in [...])`) are significantly slower (~7x) than using the built-in C-optimized tuple matching support (e.g., `s.startswith((...))`). This is a common performance anti-pattern.
**Action:** Always use `.startswith((...))` and `.endswith((...))` with a static tuple of prefixes or suffixes instead of `any()` with a generator expression when checking multiple string patterns.
