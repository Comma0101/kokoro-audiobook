from audiobook.normalize import normalize_for_speech

def test_normalization():
    cases = {
        'Dr. Smith spent $4.2M in the 1990s (see e.g. [3]).': 'Doctor Smith spent four point two million dollars in the 1990s (see for example).',
        '$50,000': 'fifty thousand dollars',
        'In 1990 he won.': 'In nineteen ninety he won.',
        '30% & up': 'thirty percent and up',
        '$1,250.50': 'one thousand, two hundred and fifty point five dollars',
        'Main St.': 'Main Saint',  # known existing behavior
    }
    
    for input_text, expected_substring in cases.items():
        out = normalize_for_speech(input_text)
        print(f"Input: {input_text}\nOutput: {out}\n")
        assert expected_substring in out, f"Expected '{expected_substring}' in '{out}'"
        
    print("All normalizer tests passed!")

if __name__ == '__main__':
    test_normalization()
