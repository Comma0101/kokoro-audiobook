# Coding Agent Instructions — Phase 1.5 fixes, then proceed to UI

Phase 1.5 review: **good.** Adapter pattern, URL source, streaming WAV, central
`sanitize_filename`, `write_srt` flag, escaped concat, normalizer — all landed and working.
The URL source is correct (`trafilatura.bare_extraction` returns a `Document`; `getattr` is right).

Two **real normalizer bugs** were found by running the code. Fix these, then proceed to the
web UI per `AGENT_INSTRUCTIONS_PHASE3_UI.md` (that spec is approved as-is).

---

## FIX 1 — currency with thousands separators is mangled (high priority)
`normalize.py` currency regex `\$(\d+(?:\.\d+)?)([MBK])?` captures only `$50` from `$50,000`,
leaving `,000`, which the later number pass reads as a stray "zero".

**Proof (current output):**
```
'$50,000'  ->  'fifty dollars,zero'      # WRONG
```
**Target:**
```
'$50,000'  ->  'fifty thousand dollars'
'$4.2M'    ->  'four point two million dollars'   # keep working
'$1,250.50'->  'one thousand two hundred fifty point five dollars'  (or similar, sane)
```
Fix: make the currency regex consume the **full** number including comma groups and decimals
before the optional `M/B/K` suffix, e.g. `\$\s?(\d[\d,]*(?:\.\d+)?)\s?([MBKmbk])?`. Strip commas
from the captured number, convert with `num2words`, append the scale word + "dollars". Handle
lowercase `m/b/k` too. Run currency **before** the generic number pass (as now), but ensure the
generic pass can't re-touch what currency already converted.

## FIX 2 — years read as cardinals (high priority for narration quality)
**Proof:**
```
'In 1990'  ->  'In one thousand, nine hundred and ninety'   # sounds wrong
```
**Target:** `'In 1990' -> 'In nineteen ninety'`.
Fix: in the number pass, if a bare integer is a plausible **year** (e.g. 1100–2099, 4 digits,
not comma-grouped, not part of a currency/percent), convert with `num2words(n, to='year')`
(which yields "nineteen ninety"). Otherwise use the cardinal form as today. Keep it conservative
— only the 4-digit year window, so quantities like `2048` MB stay cardinal only if you can tell;
when ambiguous, the year reading is the safer default for prose.

## Minor (optional, only if quick — don't over-engineer)
- `Main St.` → "Main Saint" is wrong (should be Street). Either make `St.` context-aware
  (preceding capitalized word → Street) or leave `St.` unchanged. Don't guess badly.
- Removing `[3]` then converting `e.g.` leaves `"(see for example )"` with a dangling space
  before `)`. Collapse `\(\s+` / `\s+\)` and empty `()` at the end. Cosmetic.
- `1990s` (decades) and `5pm` are left untouched today; misaki handles them acceptably. Leave them.

## Regression tests (extend `test_norm.py` into real asserts)
Convert the throwaway script into assertions so these don't regress:
```python
cases = {
    'Dr. Smith spent $4.2M in the 1990s (see e.g. [3]).':
        # Doctor ... four point two million dollars ... for example (no stray symbols)
    '$50,000':       'fifty thousand dollars',
    'In 1990 he won.': 'In nineteen ninety he won.',
    '30% & up':      'thirty percent  and  up',   # adjust spacing to actual
}
```
Pin the two fixed cases exactly; for the long sentence assert key substrings
(`'four point two million dollars'`, `'for example'`, no `'$'`, no `'[3]'`).
Run: `.venv/bin/python -m pytest test_norm.py -q` (add `uv pip install pytest`) or keep it a
plain asserting script. Show it passing.

---

## Then: build the Web UI
Proceed with `AGENT_INSTRUCTIONS_PHASE3_UI.md` exactly as written. Reminders that matter most:
1. **Extract `generate_audiobook()` first** so CLI + server share one engine path (and emit
   `cues.json` per chapter for the player).
2. **One worker, one persistent `KPipeline`** (single GPU; serialize jobs).
3. **Phone-first + offline**: PWA service-worker caching + Media Session API (lock-screen/background audio).
4. **Auth seam OFF by default** via `AUDIOBOOK_TOKEN`; harden uploads (size cap, extension whitelist).
5. **HTTPS is required** for PWA/offline/background audio — Cloudflare Tunnel in the RUNBOOK.

## Verification
- Normalizer: the asserts above pass; re-run a real TXT and confirm no `$`, stray digits, or
  "dollars,zero" artifacts in a sampled chapter's SRT.
- No regression: Alice EPUB + `trading_psychology.txt` still produce aligned SRT (last cue end
  within ~0.3s of MP3 duration).
- Then the Phase 3 verification gates in `AGENT_INSTRUCTIONS_PHASE3_UI.md` §8.
