## 2024-05-18 - [Optimization of `startswith` and `endswith` checks]
**Learning:** Generator expressions with `any()` for string prefix/suffix checks (e.g. `any(val.startswith(p) for p in iter)`) are about 10x slower than using C-optimized tuple matching `val.startswith(tuple_of_prefixes)`. The tuple must be statically defined or converted once, not on every call.
**Action:** Replace `any(path.endswith(s) for s in list)` with `path.endswith(tuple)` and `any(val.startswith(p) for p in list)` with `val.startswith(tuple)` in hot paths like verification engine and resolver.
