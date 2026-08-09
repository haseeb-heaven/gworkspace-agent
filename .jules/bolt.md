## 2024-11-20 - [Performance] Optimization using tuples for str.endswith and str.startswith
**Learning:** Found multiple usages of `any(path.endswith(s) for s in singular_suffixes)` with a list in Python. Using `tuple` with `startswith` and `endswith` executes faster since the string methods support tuples natively and are implemented in C.
**Action:** Replace `any(...)` with `.endswith(tuple(...))` or `.startswith(tuple(...))` whenever possible for improved execution speed.
