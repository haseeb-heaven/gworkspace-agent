## 2024-08-16 - Optimize string prefix matching
**Learning:** Using `any(s.startswith(p) for p in [...])` incurs significant Python generator overhead. Passing a tuple directly to `str.startswith((p1, p2, ...))` leverages C-level optimization and is ~10x faster.
**Action:** Always use a static tuple with `startswith`/`endswith` instead of generator expressions when checking multiple string prefixes/suffixes.
