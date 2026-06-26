import re
from num2words import num2words

def normalize_for_speech(text: str, llm=None) -> str:
    # Phase 4 hook for LLM
    if llm is not None:
        pass

    # Noise
    text = re.sub(r'https?://[^\s]+', 'link', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'[*`#]', '', text)
    
    # Symbols
    text = text.replace('&', ' and ')
    text = text.replace('%', ' percent ')
    text = text.replace('@', ' at ')
    text = text.replace('~', ' about ')
    text = re.sub(r'[/]', ' slash ', text)
    text = re.sub(r'[—–]', ', ', text)
    
    # Abbreviations
    text = re.sub(r'\bDr\.', 'Doctor', text)
    text = re.sub(r'\bMr\.', 'Mister', text)
    text = re.sub(r'\bMrs\.', 'Missus', text)
    text = re.sub(r'\bMs\.', 'Miss', text)
    text = re.sub(r'\bSt\.', 'Saint', text)
    text = re.sub(r'\be\.g\.', 'for example', text)
    text = re.sub(r'\bi\.e\.', 'that is', text)
    text = re.sub(r'\betc\.', 'et cetera', text)
    text = re.sub(r'\bvs\.', 'versus', text)
    text = re.sub(r'\bNo\.', 'number', text)
    
    # Clean dangling space from removing [3] before parens
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'\(\)', '', text)
    
    # Currency
    def replace_currency(match):
        num_str = match.group(1).replace(',', '')
        suffix = match.group(2)
        try:
            val = float(num_str) if '.' in num_str else int(num_str)
            word = num2words(val)
        except:
            word = match.group(1)
            
        if suffix:
            s = suffix.upper()
            if s == 'M': word += ' million'
            elif s == 'B': word += ' billion'
            elif s == 'K': word += ' thousand'
            
        return word + " dollars"
        
    text = re.sub(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?([MBKmbk])?', replace_currency, text)
    
    # Numbers and Years
    def replace_num(match):
        num_str = match.group(0).replace(',', '')
        try:
            if '.' in num_str:
                return num2words(float(num_str))
                
            val = int(num_str)
            # Year logic: 1100-2099, exactly 4 chars, no commas in original string
            if 1100 <= val <= 2099 and len(match.group(0)) == 4:
                return num2words(val, to='year')
                
            return num2words(val)
        except:
            return match.group(0)
            
    text = re.sub(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', replace_num, text)
    
    # Clean up whitespace
    text = " ".join(text.split())
    return text

# Remove characters from scripts the English pipeline can't speak.
# Keep Latin, digits, common punctuation/symbols, and whitespace.
_NON_LATIN = re.compile(
    r'[　-〿぀-ヿ㐀-䶿一-鿿'
    r'가-힯Ѐ-ӿ＀-￯]+'
)

def strip_non_latin(text: str) -> str:
    text = _NON_LATIN.sub(' ', text)
    return " ".join(text.split())
