import re

def sanitize_filename(name: str) -> str:
    # Allow unicode words (\w), spaces, dots, hyphens
    clean = re.sub(r'[^\w\s.-]', '', name)
    clean = " ".join(clean.split())
    clean = clean.strip()
    if not clean:
        clean = "untitled"
    # cap length
    return clean[:80].strip()
