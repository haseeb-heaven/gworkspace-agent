## 2024-07-07 - Optimize String Prefix and Suffix Checks
**Learning:** Checking for multiple string prefixes or suffixes in Python using generator expressions (e.g. `any(val.startswith(p) for p in prefixes)`) is significantly slower than using `str.startswith(tuple_of_prefixes)`. Passing a literal tuple to `startswith` or `endswith` is implemented in C and evaluates an order of magnitude faster.
**Action:** Always prefer using a literal tuple with `.startswith()` or `.endswith()` rather than looping or using generator expressions when checking against multiple literal string values.
