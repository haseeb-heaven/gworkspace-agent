## 2024-05-24 - [Python String Prefix/Suffix Checks]
**Learning:** Checking for multiple string prefixes or suffixes using a generator expression like `any(s.startswith(prefix) for prefix in prefixes)` is significantly slower than passing a tuple directly to `startswith` or `endswith`, because the tuple implementation is written in C and avoids Python interpreter overhead on every item.
**Action:** Always prefer using a literal tuple with `startswith` and `endswith` instead of `any()` generator expressions when checking multiple prefixes/suffixes.
