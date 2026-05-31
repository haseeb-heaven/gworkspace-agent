## 2024-05-24 - Optimizing startswith/endswith with Tuples
**Learning:** Checking for multiple string prefixes/suffixes using a generator expression inside `any()` is slow in Python.
**Action:** Use `str.startswith(tuple_of_strings)` or `str.endswith(tuple_of_strings)`, which are implemented in C and execute much faster. Always pass a tuple, not a list or generator.
