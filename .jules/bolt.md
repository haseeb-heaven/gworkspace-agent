## 2024-06-26 - Optimize string endswith checks
**Learning:** Checking for multiple string suffixes in Python using a generator expression inside `any()` (e.g. `any(path.endswith(s) for s in list_of_suffixes)`) is an anti-pattern for performance because it introduces python-level loop and generator overhead. `str.endswith()` accepts a tuple of strings directly.
**Action:** Always prefer passing a static tuple of prefixes or suffixes directly to `str.startswith()` or `str.endswith()` as this evaluates entirely in C and executes significantly faster.
