import time
import re

def original_extract_keywords(text: str) -> list[str]:
    keywords: list[str] = []
    for match in re.findall(r"""['"]([^'"]{2,80})['"]""", text):
        keywords.append(match.strip().lower())

    stop_words = {"the", "and", "or"}
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    for word in words:
        if word not in stop_words and word not in [k.lower() for k in keywords]:
            keywords.append(word)
    return keywords

def optimized_extract_keywords(text: str) -> list[str]:
    keywords: list[str] = []
    for match in re.findall(r"""['"]([^'"]{2,80})['"]""", text):
        keywords.append(match.strip().lower())

    stop_words = {"the", "and", "or"}
    seen_keywords = {k.lower() for k in keywords}
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    for word in words:
        if word not in stop_words and word not in seen_keywords:
            keywords.append(word)
            seen_keywords.add(word)
    return keywords

test_text = "This is a long test text with many many words to test the performance of the list comprehension inside the loop. " * 100

start = time.time()
for _ in range(1000):
    original_extract_keywords(test_text)
orig_time = time.time() - start

start = time.time()
for _ in range(1000):
    optimized_extract_keywords(test_text)
opt_time = time.time() - start

print(f"Original: {orig_time:.5f}s")
print(f"Optimized: {opt_time:.5f}s")
print(f"Speedup: {orig_time / opt_time:.2f}x")
