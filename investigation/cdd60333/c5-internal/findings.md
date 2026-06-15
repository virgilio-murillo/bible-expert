# Bible-Expert OT Quality & Unified HTML Generator — Internal Investigation

## Summary

The study.html generator has partial OT support (WLC + LXX morphology loads correctly, LXX-ES translation works) but **critical JS template bugs** prevent morphological explanation for both Hebrew and LXX words. The unified_html_generator has **zero OT-specific handling** — it was built entirely for NT Greek workflows.

---

## 1. unified_html_generator.py — OT Feature Gaps

### What it DOES use from chapter_data:
- `morphology` — renders word-by-word (line 751-753), but always in `.greek-line` div
- `patristic` — grouped by verse with themes (works for OT books that have patristic data)
- `apparatus` — TC section with collation table and verdicts
- `greek_commentaries` — exegesis section (requires commentaries table)
- `xrefs` — sidebar cross-references

### What is MISSING for OT:
| Feature | study.html | unified_html |
|---------|-----------|--------------|
| WLC RTL direction | ✅ `.verse-line.original { direction: rtl }` (line 762) | ❌ Uses `.greek-line` (LTR) |
| WLC label | ✅ `<span class="vlabel">WLC</span>` | ❌ No label |
| LXX parallel line | ✅ `renderLxxMorph()` with hover/click | ❌ Not rendered |
| LXX-ES translation | ✅ Displayed below LXX line (line 854-855) | ❌ Not used |
| LXX morphology data | ✅ Loaded as `D.lxx_morphology` | ❌ Not in JS template |
| OT-aware fallback in JS | ✅ Checks `isOT` flag (line 829) | ❌ No `isOT` concept |

**unified_html_generator.py line 751-758** — JS rendering only handles:
1. `D.morphology[v.v]` (works for WLC since it's loaded into `morphology`)
2. `D.parallel.MorphGNT` fallback
3. `D.parallel.SBLGNT` fallback

No mention of `D.parallel.WLC`, `D.lxx_morphology`, or `D.lxx_spanish` anywhere in the unified generator.

---

## 2. study.html JS Template — Hebrew Morphology Bug (CRITICAL)

### The `explainEnding(w)` function (study_html_generator.py line 966)

This function provides the grammatical breakdown popup. It parses RMAC format exclusively:

```
if (rmac === 'CONJ') ...       // exact match
if (rmac.startsWith('PREP'))   // Greek preposition
if (rmac.startsWith('N-'))     // Noun: "N-NSM"
if (rmac.startsWith('A-'))     // Adjective: "A-NSM"  
if (rmac.startsWith('T-'))     // Article: "T-NSM"
if (rmac.startsWith('V-'))     // Verb: "V-AAI-3S"
```

**WLC morph codes** are OSHM format: `HVqp3ms`, `HNcmsa`, `HR/Ncfsa`, `HTd/Ncmpa`

- First char `H` = Hebrew language marker
- None of these match any RMAC prefix check
- `H` is not in `pronounTypes` object (`P,D,R,X,I,S,F,K,C,Q`)
- **Result**: Falls to final fallback (line 1083):
  ```js
  if (form !== lemma) return header + `<span>Forma flexionada de ${lemma}</span>`;
  return '';
  ```
  
This means Hebrew words get **no case, gender, number, tense, or voice explanation** — just "Forma flexionada de [lemma]".

### The `verbTenseEs(rmac)` function (line 887)

```js
function verbTenseEs(rmac) {
  if (!rmac || !rmac.startsWith('V-')) return '';
  ...
}
```

Hebrew verb codes like `HVqp3ms` → returns empty string. No tense/aspect info shown on hover.

### The `contextualMeaning(w)` function (line 952)

```js
if (!w.m || !w.m.startsWith('V-')) return '';
```

Hebrew verbs → returns empty string. No contextual meaning on hover tooltip.

---

## 3. LXX Morphology Code Mismatch (CRITICAL)

LXX morph codes use **dot notation**: `V.AAI3S`, `N.NSM`, `RA.NSM`, `C`, `P`

The `explainEnding` function checks for **dash notation**: `V-`, `N-`, `A-`, `T-`

```
"V.AAI3S".startsWith('V-')  → false  (dot not dash)
"N.NSM".startsWith('N-')    → false
"RA.NSM".startsWith('A-')   → false  (starts with "RA")
```

**Result**: ALL LXX words also fall to the generic fallback. No grammatical explanation.

However, the `openLxxStudy` function (line 1127) provides a simpler popup that just shows the raw morph code — it doesn't attempt to parse it. So LXX words show their raw code `V.AAI3S` but without explanation.

---

## 4. `openWordStudy` External Links — Greek-Only URLs

**study_html_generator.py line ~1215-1220:**

```js
<li><a href="https://www.blueletterbible.org/lexicon/${w.s}/kjv/tr/0-1/">Blue Letter Bible</a></li>
<li><a href="https://biblehub.com/greek/${(w.s||'').replace('G','')}.htm">BibleHub</a></li>
<li><a href="https://www.perseus.tufts.edu/hopper/morph?l=${encodeURIComponent(w.l)}&la=greek">Perseus</a></li>
<li><a href="https://logeion.uchicago.edu/${encodeURIComponent(w.l)}">Logeion</a></li>
<li><a href="https://www.stepbible.org/?q=strong=${w.s}">STEP Bible</a></li>
```

For Hebrew words with H-numbers (e.g., H7225):
- **BlueLetter**: URL uses `/tr/0-1/` (Greek Textus Receptus) — should be `/wlc/0-1/` for Hebrew
- **BibleHub**: Uses `/greek/` path — should be `/hebrew/` for H-numbers
- **Perseus**: `la=greek` param — should be `la=hebrew` (though Perseus Hebrew support is limited)
- **Logeion**: Greek-only dictionary, won't find Hebrew lemmas
- **STEP Bible**: Works correctly for both G and H numbers ✅

---

## 5. `gather_chapter_data` Book Name Candidates (WORKING CORRECTLY)

The `candidates` list is populated by `get_all_db_names(book)` in books.py (line 124):
```python
def get_all_db_names(book: str) -> list[str]:
    # Returns [canonical_name] + [all aliases]
    # e.g., get_all_db_names("Genesis") → ["Genesis", "Gen", "Gn", "Génesis", ...]
```

DB uses abbreviated names for morphology/verses: `Gen`, `Exod`, `Ps`, etc.
The `for b in candidates:` loop tries each name until it finds rows.

**Verified**: This works correctly. Example: 
- Morphology WLC: book=`Gen` → matched by candidates[1] 
- Patristic: book=`Genesis` → matched by candidates[0]
- Cross_refs: book=`Genesis` → matched by candidates[0]

---

## 6. DB Word Count Consistency (NO ISSUES)

Tested WLC morphology word count vs verse text word count:
```sql
SELECT ... HAVING abs(morph_words - verse_word_approx) > 3
-- 0 rows returned
```

All 306,785 WLC morphology words align perfectly with their verse text word counts. The sub-verse handling (9a, 13a merged into parent verse with continuous word_pos) works correctly.

---

## 7. `exegetical` Field & `greek_commentaries` for OT

### Commentaries table coverage:
- **27 NT books only** (Matthew through Revelation)
- **Zero OT books** — Robertson's Word Pictures, Vincent's, Expositor's, Meyer's, Bengel's, Alford's are all NT commentaries
- Sources: `robertson`, `vincent`, `expositor`, `meyer`, `bengel`, `alford`

### Impact on OT chapters:
- `data["greek_commentaries"]` will be empty dict `{}`
- The "📖 N exégesis" button will not appear (code: `if (commCount > 0)`)
- The `exegetical` field is only set when `data["morphology"]` exists — this is true for OT (WLC loaded into morphology), but the grounded exegetical LLM synthesis (`_generate_grounded_exegetical`) requires commentaries data

### Patristic table OT coverage:
| Book | Entries |
|------|---------|
| Psalms | 21,625 |
| Genesis | 9,266 |
| Isaiah | 5,206 |
| Job | 4,287 |
| Exodus | 2,253 |
| Jeremiah | 1,787 |
| Ezekiel | 1,544 |
| Daniel | 1,389 |

Good patristic coverage for major OT books. The patristic section works for OT.

---

## 8. NT vs OT Feature Comparison

| Feature | NT Chapter | OT Chapter |
|---------|-----------|------------|
| Word-by-word morphology | ✅ MorphGNT with full RMAC parsing | ⚠️ WLC displayed but NO parsing |
| Grammatical explanation popup | ✅ Case, gender, number, tense, voice | ❌ Only "Forma flexionada de..." |
| Verb tense badge on hover | ✅ "⏱ Aoristo, Activa, Indicativo" | ❌ Empty |
| Contextual meaning on hover | ✅ "habiendo dicho", "creyendo" | ❌ Only gloss/es fallback |
| Compound word decomposition | ✅ prefix + root + suffix breakdown | ❌ Works if data exists (check compounds table) |
| LXX parallel line with hover | N/A (NT) | ✅ Displays with gloss tooltip |
| LXX-ES literal translation | N/A (NT) | ✅ Claude Opus cached |
| LXX morphology explanation | N/A | ❌ Code format mismatch (dot vs dash) |
| Exegetical commentaries | ✅ Robertson, Vincent, etc. | ❌ No data in table |
| Patristic commentary | ✅ Good coverage | ✅ Good for Psalms/Genesis/Isaiah |
| Textual apparatus | ✅ From apparatus table | ❌ No OT variants in table |
| Cross-references | ✅ Full coverage | ✅ Full coverage |
| External links (word study) | ✅ All links work for G-numbers | ❌ 4/5 links broken for H-numbers |
| RTL text direction | N/A | ✅ study.html has it; ❌ unified doesn't |

---

## 9. Recommendations for OT Parity

### Priority 1 (High Impact, Medium Effort):
1. **Add Hebrew OSHM parser to `explainEnding`** — Parse codes like `HVqp3ms`:
   - `H` = Hebrew
   - `V` = Verb, `N` = Noun, `A` = Adjective, `T` = Article/Particle
   - `q` = Qal, `p` = Piel, `h` = Hiphil, etc.
   - Person, gender, number suffixes
   
2. **Add LXX morphology parser** — Convert dot notation (`V.AAI3S`) to dash notation (`V-AAI3S`) before passing to existing RMAC parser, OR add a dot-format branch in `explainEnding`

3. **Fix external links for Hebrew** — Detect H-prefix in Strong's number and use:
   - BlueLetter: `/wlc/0-1/` instead of `/tr/0-1/`
   - BibleHub: `/hebrew/` instead of `/greek/`
   - Replace Perseus/Logeion with Hebrew-appropriate resources (e.g., HALOT, BDB)

### Priority 2 (Medium Impact, Low Effort):
4. **Add OT-specific handling to unified_html_generator.py**:
   - Add `isOT` detection (check if `D.parallel.WLC` exists)
   - Render WLC line with RTL direction
   - Render LXX line with morphology hover
   - Display LXX-ES below LXX

5. **Add Hebrew verb conjugation labels** — Build OSHM equivalent of `verbTenseEs`:
   - Qal/Piel/Hiphil/Niphal etc. stem names
   - Perfect/Imperfect/Participle/Imperative aspect
   - Person/gender/number

### Priority 3 (Lower Priority):
6. **OT textual apparatus** — The apparatus table only covers NT. Could add OT variants (BHS critical apparatus, DSS variants)
7. **OT exegetical sources** — Add Hebrew commentaries (Keil-Delitzsch, Gesenius, HALOT notes)
8. **Compound prefix parsing for Hebrew** — Hebrew words with prefixes (בְּ/רֵאשִׁית = ב + ראשׁית) should show prefix decomposition

---

## 10. Specific Code Locations for Fixes

| Fix | File | Line(s) | What to Change |
|-----|------|---------|----------------|
| Hebrew OSHM parser | study_html_generator.py | 966-1083 | Add `if (rmac[0]==='H')` branch in `explainEnding` |
| Hebrew verb labels | study_html_generator.py | 887-896 | Add OSHM verb stem/aspect parsing |
| LXX code normalization | study_html_generator.py | 966 | Convert `V.AAI3S`→`V-AAI3S` at top of function |
| Hebrew external links | study_html_generator.py | 1211-1220 | Add `const isHeb = (w.s||'').startsWith('H')` conditional |
| Unified OT rendering | unified_html_generator.py | 750-758 | Add WLC/LXX/lxx_spanish branches in JS |
| Unified RTL styling | unified_html_generator.py | 638 | Add `.greek-line.rtl { direction: rtl; font-family: 'SBL Hebrew' }` |
| Contextual meaning | study_html_generator.py | 952 | Add Hebrew participle/infinitive patterns |
