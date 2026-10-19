## 2024-05-13 - Python Prefix Checking Performance
**Learning:** Found multiple instances of string prefix checking using long chains of `startswith()` calls (e.g., `model_name.startswith("groq/") or model_name.startswith("openrouter/") or ...`). This is slower than using a single `startswith()` call with a tuple of prefixes (e.g., `model_name.startswith(("groq/", "openrouter/", ...))`) since the latter is optimized in C.
**Action:** Replace chains of `startswith()` or `endswith()` calls on the same variable with a single call passing a tuple of prefixes/suffixes.
## 2024-05-14 - Python Suffix Checking Performance
**Learning:** Similar to prefix checking, string suffix checking using long chains of `endswith()` calls (e.g., `k.endswith("Url") or k.endswith("Link")`) is slower than using a single `endswith()` call with a tuple of suffixes (e.g., `k.endswith(("Url", "Link"))`) since the latter is optimized in C.
**Action:** Replace chains of `endswith()` calls on the same variable with a single call passing a tuple of suffixes.
