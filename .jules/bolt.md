## 2024-05-13 - Python Prefix Checking Performance
**Learning:** Found multiple instances of string prefix checking using long chains of `startswith()` calls (e.g., `model_name.startswith("groq/") or model_name.startswith("openrouter/") or ...`). This is slower than using a single `startswith()` call with a tuple of prefixes (e.g., `model_name.startswith(("groq/", "openrouter/", ...))`) since the latter is optimized in C.
**Action:** Replace chains of `startswith()` or `endswith()` calls on the same variable with a single call passing a tuple of prefixes/suffixes.

## 2024-10-18 - Dictionary Substring Lookups
**Learning:** Using a generator expression like `any(k in p for k in map)` to check if a dictionary key is a substring of a token is an $O(N)$ operation that becomes a bottleneck during regex substitutions.
**Action:** For path-like tokens (e.g. `task-1.id`), tokenizing the prefix (`p.split('.')[0].split('[')[0] in map`) allows for an $O(1)$ dictionary lookup, yielding a ~13x speedup.
