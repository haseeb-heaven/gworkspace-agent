## 2024-05-18 - [Optimize `startswith` checks]
**Learning:** Checking against a collection of prefixes using a generator expression inside `any()` (e.g. `any(val.startswith(p) for p in iter)`) is significantly slower than using a tuple directly with `.startswith(tuple)` because Python handles the tuple matching natively in C without the generator overhead.
**Action:** When validating multiple string prefixes, always use `str.startswith((prefix1, prefix2, ...))` instead of `any(str.startswith(p) for p in [prefix1, prefix2, ...])`.
