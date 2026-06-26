import re

HAN = re.compile(r'[一-鿿㐀-䶿]')      # CJK ideographs
LATIN = re.compile(r'[A-Za-z]')

def detect_lang(text: str, threshold: float = 0.15) -> str:
    """Return 'z' if the text is Chinese-dominant, else 'a'."""
    han = len(HAN.findall(text))
    latin = len(LATIN.findall(text))
    if han == 0:
        return 'a'
    ratio = han / (han + latin) if (han + latin) else 0
    return 'z' if ratio >= threshold else 'a'
