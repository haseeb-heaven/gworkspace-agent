## 2024-11-20 - [Optimize startswith/endswith with tuples]
**Learning:** Using `startswith(tuple)` is implemented in C and is significantly faster than using generator expressions like `any(x.startswith(p) for p in [...])`.
**Action:** Always prefer passing a static tuple of prefixes/suffixes to `startswith`/`endswith` over chained conditions or `any()` generator expressions.
