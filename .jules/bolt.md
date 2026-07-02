## 2026-07-02 - str.endswith() Performance Optimization
**Learning:** Checking string suffixes against multiple values using `any(path.endswith(s) for s in list)` is ~5-10x slower than passing a tuple directly to `endswith`: `path.endswith(tuple)`. The latter is implemented in C and runs significantly faster.
**Action:** When checking for multiple prefixes or suffixes, always use `str.startswith(tuple_of_prefixes)` or `str.endswith(tuple_of_suffixes)`.
