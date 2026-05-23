## 2024-05-23 - Optimize string prefix checking
**Learning:** Checking against multiple string prefixes using `any(s.startswith(prefix) for prefix in [...])` evaluates Python bytecode in a generator expression.
**Action:** Use `s.startswith(tuple_of_prefixes)` instead, as passing a tuple to `str.startswith()` is implemented directly in C and executes significantly faster, especially on hot paths like validation or policy scanning.
