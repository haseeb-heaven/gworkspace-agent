## 2024-08-03 - Use tuples for string prefix/suffix checking
**Learning:** The codebase currently uses generator expressions like `any(s.startswith(prefix) for prefix in prefixes)` which iterate in Python. Passing a tuple of prefixes to `str.startswith(prefixes)` is implemented in C and executes significantly faster. This is a common codebase-specific performance anti-pattern found across multiple files.
**Action:** Always prefer `str.startswith(tuple_of_strings)` or `str.endswith(tuple_of_strings)` when checking multiple prefixes or suffixes, provided the tuple is a static literal.
