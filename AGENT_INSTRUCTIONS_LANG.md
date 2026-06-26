# Coding Agent Instructions — Mixed-language handling (Chinese + English)

## Problem (confirmed by reproduction)
The English pipeline (`lang_code='a'`) replaces every character it can't read with the literal
words **"Chinese letter" / "Japanese letter"** and speaks them — so any CJK text in a URL/article
becomes gibberish like `ʧˈIniz lˌɛTəɹ` repeated.

Verified facts to build on:
- The **Chinese pipeline (`lang_code='z'`) handles mixed CN+EN in a single pass**: it phonemizes
  Chinese correctly AND passes embedded English words through for its acoustic model to read
  (proven: `你好…Python 和 AI` and `The CEO said 我很高兴 to be here` both worked, no gibberish).
- The gibberish ONLY happens with the English pipeline hitting non-Latin text.

## The rule to implement (decided)
Choose the pipeline **per chapter** by detecting dominant script:
- **English-dominant** → pipeline `'a'`, English voice (`af_heart`), **strip all non-Latin
  characters first** (kills the "Chinese letter" bug; also covers Japanese/Korean/Cyrillic).
- **Chinese-dominant** → pipeline `'z'`, Chinese voice (default `zf_xiaobei`), **keep everything**
  (the model reads the embedded English; accept a slight accent on English — that's expected).

Scope is **Chinese + English only** right now. Other languages are not "spoken"; in English mode
they're stripped, which is the safe fallback.

---

## 1. Language detection (`audiobook/lang.py`)
```python
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
```
- Threshold ~0.15 means: a few stray Han chars in an English article stay English (and get
  stripped); a Chinese article full of English technical terms still routes to Chinese. Make the
  threshold a constant the user can tune; don't hardcode it in three places.

## 2. Strip non-Latin for English mode (`normalize.py`)
Add and apply **only in the English branch**, before chunking:
```python
# Remove characters from scripts the English pipeline can't speak.
# Keep Latin, digits, common punctuation/symbols, and whitespace.
_NON_LATIN = re.compile(
    r'[　-〿぀-ヿ㐀-䶿一-鿿'
    r'가-힯Ѐ-ӿ＀-￯]+'
)
def strip_non_latin(text: str) -> str:
    text = _NON_LATIN.sub(' ', text)          # CJK, kana, hangul, cyrillic, fullwidth forms
    return " ".join(text.split())
```
Apply order in English mode: `normalize_for_speech(...)` → `strip_non_latin(...)` → `chunk_text`.
In Chinese mode, do **not** run `strip_non_latin`, and **skip the English narration normalizer**
(its `num2words`/abbreviation rules are English-specific and will mangle Chinese, e.g. turning
`2024年` into English digits). At most do whitespace cleanup in Chinese mode.

## 3. Pipeline cache (replace the single `init_pipeline` call)
The engine currently loads one pipeline up front. Switch to a lazy, memoized loader so a mixed
book can use both without reloading (Kokoro is 82M params — loading two is cheap on the 4070):
```python
_PIPELINES = {}
def get_pipeline(lang_code: str):
    if lang_code not in _PIPELINES:
        _PIPELINES[lang_code] = init_pipeline(lang_code)
    return _PIPELINES[lang_code]
```

## 4. Wire it into the per-chapter loop (`cli.py`, and the future `generate_audiobook`)
For each chapter:
```python
lang = args.lang if args.lang != 'auto' else detect_lang(chapter.text)
pipeline = get_pipeline(lang)
if lang == 'z':
    voice = args.voice_zh
    text = " ".join(chapter.text.split())          # no English normalizer, no strip
else:
    voice = args.voice                              # af_heart
    text = chapter.text
    if not args.no_normalize:
        text = normalize_for_speech(text)
    text = strip_non_latin(text)                    # kill the gibberish
chunks = chunk_text(text)
... synth with `pipeline` and `voice` ...
```
Note: `chunk_text`'s split regex `(?<=[.!?])\s+` won't split on Chinese full stops `。`. Add
`。！？` to the split pattern (or branch the splitter by lang) so Chinese chapters still chunk
into reasonable segments and don't feed one giant string to the model.

## 5. CLI flags
- `--lang` default changes to **`auto`** (was `a`). Keep `a`/`z` as explicit overrides.
- Add `--voice-zh` (default `zf_xiaobei`) for the Chinese voice; `--voice` stays the English default.
- Print the chosen lang/voice per chapter in the progress line so routing is visible.

---

## Verification (show evidence)
1. **No more gibberish:** run on text containing `你好世界` in an otherwise English doc → confirm
   the SRT/audio has the Chinese simply absent (stripped), and **no "Chinese letter"** anywhere.
   Quick check: `grep -i "chinese letter" out/**/**.srt` returns nothing (it never will once
   stripped, but also confirm no weird residue).
2. **Chinese-dominant reads both:** run on a mostly-Chinese paragraph with embedded English
   (e.g. the `你好…Python 和 AI` sample) → routes to `'z'`, audio produced, English terms audible.
3. **Routing logic unit test:** `detect_lang` returns `'a'` for English with a stray Han char,
   `'z'` for a Chinese paragraph with English terms. Pin a couple cases in a test.
4. **No regression:** pure-English `trading_psychology.txt` and Alice EPUB still route to `'a'`
   and produce aligned SRT (last cue end within ~0.3s of MP3 duration).
5. **Chinese chunking:** a long Chinese chapter splits into multiple cues (not one giant blob),
   confirming the `。！？` split addition works.

## Out of scope (note, don't build)
- Japanese/Korean as *spoken* languages (only CN+EN now). Be aware of the routing edge: because
  Japanese **kanji are Han characters**, a Han-heavy Japanese doc routes to `'z'` and will be
  *mispronounced* as Chinese (not stripped). Korean/Cyrillic (no Han) route to `'a'` and ARE
  stripped. This is acceptable for now (CN+EN scope); if Japanese matters later, add a kana check
  to `detect_lang` that routes kana-containing text away from `'z'`.
- Per-sentence dual-voice routing within one chapter (we chose whole-chapter routing for a
  consistent narrator). Revisit only if the accent on English in Chinese mode bothers the user.
