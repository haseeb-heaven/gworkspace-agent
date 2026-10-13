## 2024-05-13 - Python Prefix Checking Performance
**Learning:** Found multiple instances of string prefix checking using long chains of `startswith()` calls (e.g., `model_name.startswith("groq/") or model_name.startswith("openrouter/") or ...`). This is slower than using a single `startswith()` call with a tuple of prefixes (e.g., `model_name.startswith(("groq/", "openrouter/", ...))`) since the latter is optimized in C.
**Action:** Replace chains of `startswith()` or `endswith()` calls on the same variable with a single call passing a tuple of prefixes/suffixes.
## 2024-05-14 - Python String Prefix/Suffix Checking Optimization
**Learning:** Found string prefix/suffix checking loops using multiple consecutive `startswith()` or `endswith()` boolean `or` chains (e.g. `k.endswith("Url") or k.endswith("Link")`). This performs multiple method evaluations at the Python level.
**Action:** Replace `or` chains of string suffix/prefix checks with a single C-optimized tuple match (e.g. `k.endswith(("Url", "Link"))`). This is evaluated in C and is significantly faster in tight processing loops like verification engines.
