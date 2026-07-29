## 2024-07-29 - [Optimization of String Methods]
**Learning:** Using `any(val.startswith(p) for p in [...])` generator expressions in Python is significantly slower (up to 10x) than passing a tuple directly to `val.startswith((...))`.
**Action:** Use `startswith` and `endswith` with a literal tuple of prefixes/suffixes instead of a generator expression when matching multiple static options.
