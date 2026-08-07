## 2024-05-18 - [Optimization] Tuple for startswith is faster than any() with a generator
**Learning:** Checking multiple prefixes with `str.startswith((...))` is about 10x faster than `any(str.startswith(p) for p in [...])` because the tuple version is implemented in C and avoids the overhead of the generator expression in Python.
**Action:** Use tuple arguments for `startswith` and `endswith` checks when evaluating static lists of prefixes/suffixes.
