## 2024-05-25 - Python prefix/suffix matching optimization
**Learning:** Using `str.startswith()` and `str.endswith()` with a tuple is implemented in C and is significantly faster than using generator expressions with `any()` in Python.
**Action:** Always use tuples with `startswith` and `endswith` instead of `any()` for multiple prefixes/suffixes checks, ensuring the tuple is statically defined.
