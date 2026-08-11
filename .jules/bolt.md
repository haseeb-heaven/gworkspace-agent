## 2024-08-11 - [Optimize String Prefix/Suffix Checking]
**Learning:** Using `any(path.endswith(s) for s in list)` or `any(path.startswith(p) for p in list)` introduces Python-level generator overhead. Python's `str.startswith()` and `str.endswith()` can directly accept a static tuple of strings, which is evaluated in C and executes significantly faster (up to ~15x faster on microbenchmarks).
**Action:** Always prefer using static tuples directly with `.startswith()` and `.endswith()` instead of generator expressions when checking for multiple prefixes or suffixes.
