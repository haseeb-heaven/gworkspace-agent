## 2024-07-08 - String prefix/suffix checking with generator expressions
**Learning:** Using `any(path.endswith(s) for s in suffixes)` is a performance anti-pattern in Python compared to passing a tuple `path.endswith(suffixes)`, because the latter is implemented in C and avoids generator overhead.
**Action:** Replace generator expressions checking `startswith`/`endswith` with the tuple approach where the suffixes/prefixes list can be converted to a tuple.
