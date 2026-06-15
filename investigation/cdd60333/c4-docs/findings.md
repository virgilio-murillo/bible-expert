# Investigation Findings: OT Quality & Unified HTML Generator

## 1. unified_html_generator.py vs study_html_generator.py — Feature Gaps

### What unified_html uses:
- `chapter_data["morphology"]` — renders Greek line via JS (`_build_unified_body` line 760-770)
- `chapter_data["patristic"]`, `chapter_data["apparatus"]`, `chapter_data["greek_commentaries"]`
- `chapter_data["spanish"]`, `chapter_data["translations"]`, `chapter_data["xrefs"]`

### What unified_html does NOT use:
- **`lxx_morphology`** — key completely absent from unified_html_generator.py
- **`lxx_spanish`** — LXX literal translation not shown
- **`parallel["WLC"]`** — Hebrew text line not rendered
- **`parallel["LXX"]`** — LXX text line not rendered
- **`compounds`** — word decomposition data ignored
- **`rmac`** — RMAC code descriptions not loaded

### Key difference:
- `study_html_generator.py` (line ~843-860): Renders WLC Hebrew line, LXX line with interactive morphology hover, and LXX-ES translation for OT chapters
- `unified_html_generator.py` (line ~760): Only renders one "Greek line" using `D.morphology` — for OT this ends up being WLC Hebrew data rendered in a Greek-styled div

### Verdict:
For OT, the unified analysis shows Hebrew morphology words (from WLC fallback in `gather_chapter_data` line 96) but treats them as if they were Greek — no separate Hebrew/LXX lines, no LXX translation.

---

## 2. study.html JS Template Bugs with OT Data

### Bug A: `renderMorph` called with WLC data (line ~1067-1073)
```javascript
function renderMorph(vnum, fallbackText) {
  const words = D.morphology[vnum];  // For OT: these are WLC Hebrew words
  ...
}
```
For OT, `D.morphology` contains WLC Hebrew words (because of the fallback at `gather_chapter_data` line 96). The hover tooltip shows the word correctly (just shows `w.g` gloss), but:

### Bug B: `explainEnding` fails silently for Hebrew codes (line ~968)
The `explainEnding` function checks `rmac.startsWith('V-')`, `rmac.startsWith('N-')`, etc. — all RMAC patterns.

**WLC codes** look like: `HVqp3ms`, `HNcmsa`, `HR/Ncfsa`, `HC/Vqw3ms`, `HTd/Ncmpa`
- They start with `H` (Hebrew), NOT `V-` or `N-`
- They use entirely different notation (OSHM = OpenScriptures Hebrew Morphology)
- Result: `explainEnding` hits the final fallback at line ~1059: `if (form !== lemma) return 'Forma flexionada de...'`
- **Impact**: No educational morphology breakdown shown for Hebrew words

### Bug C: `verbTenseEs` fails silently for Hebrew codes (line ~860)
```javascript
function verbTenseEs(rmac) {
  if (!rmac || !rmac.startsWith('V-')) return '';  // Hebrew codes: 'HVqp3ms' → empty
```
**Impact**: No verb tense explanation for Hebrew words

### Bug D: `contextualMeaning` fails for Hebrew (line ~959)
```javascript
function contextualMeaning(w) {
  if (!w.m || !w.m.startsWith('V-')) return '';  // Always empty for Hebrew
```
All the contextual meaning lookups (like `λέγω_PPP → 'llamado'`) are Greek-only.

---

## 3. NT vs OT Feature Comparison

| Feature | NT (MorphGNT) | OT (WLC + LXX) |
|---------|---------------|-----------------|
| Word-by-word hover | ✅ Full (gloss, lemma, morph) | ✅ Works (gloss from lexicon) |
| explainEnding decomposition | ✅ Full RMAC parsing | ❌ Falls to generic fallback |
| verbTenseEs | ✅ Full tense/voice/mood | ❌ Silent failure (empty string) |
| contextualMeaning | ✅ 50+ entries | ❌ None for Hebrew |
| LXX parallel line | N/A | ✅ Rendered in study.html |
| LXX-ES translation | N/A | ✅ Rendered in study.html |
| Compound decomposition | ✅ Greek compounds | ❌ Not populated for Hebrew |
| Exegetical commentary (commentaries table) | ✅ 27 books | ❌ Table is NT-only |
| Patristic | ✅ Full | ✅ Full (Genesis=9266, Psalms=21625, Isaiah=5206) |
| Cross-references | ✅ | ✅ |
| Apparatus / TC | ✅ | ✅ (OT has variants) |
| openWordStudy popup | ✅ Greek links work | ⚠️ Links broken for H-numbers |
| Unified analysis WLC line | ❌ Not rendered | ❌ Not rendered |
| Unified analysis LXX line | N/A | ❌ Not rendered |
| Unified analysis LXX-ES | N/A | ❌ Not rendered |

---

## 4. `renderMorph` and WLC Data (Hebrew OSHM Format)

**WLC morph_code format** (confirmed from DB, 306K words):
- `HNcmsa` = Hebrew, Noun, common, masculine, singular, absolute
- `HVqp3ms` = Hebrew, Verb, qal, perfect, 3rd person, masculine, singular
- `HR` = Hebrew, Preposition
- `HTd/Ncmpa` = Hebrew, article + Noun, common, masculine, plural, absolute
- `HC/Vqw3ms` = Hebrew, conjunction + Verb, qal, wayyiqtol, 3rd masculine singular

**Expected behavior**: The system should parse OSHM codes into human-readable Spanish explanations, analogous to how `explainEnding` handles RMAC for Greek.

**Current behavior**: All Hebrew morphology words get either:
- Empty string (from `verbTenseEs`, `contextualMeaning`)
- Generic "Forma flexionada de X" (from `explainEnding` fallback)

---

## 5. `openWordStudy` Hebrew Links Bug

`openWordStudy` (line ~1168-1230) generates external links:
```javascript
<li><a href="https://www.blueletterbible.org/lexicon/${w.s || ''}/kjv/tr/0-1/">Blue Letter Bible</a></li>
<li><a href="https://biblehub.com/greek/${(w.s||'').replace('G','')}.htm">BibleHub</a></li>
<li><a href="https://www.perseus.tufts.edu/hopper/morph?l=${encodeURIComponent(w.l)}&la=greek">Perseus</a></li>
```

**Bugs for Hebrew (H-numbers)**:
1. BibleHub link: `biblehub.com/greek/1254.htm` — wrong! Should be `biblehub.com/hebrew/1254.htm`
2. Perseus link: `&la=greek` — wrong! Should be `&la=hebrew` (though Perseus doesn't have Hebrew morphology)
3. Blue Letter Bible: Actually works for both G and H numbers ✅
4. Logeion: Only has Greek, not Hebrew
5. STEP Bible: Works for both ✅

---

## 6. LXX Morphology Codes vs explainEnding/verbTenseEs

**LXX morph_code format** (confirmed from DB, 623K words):
- `N.NSM` = Noun, Nominative, Singular, Masculine
- `V.AAI3S` = Verb, Aorist, Active, Indicative, 3rd Singular
- `C` = Conjunction
- `P` = Preposition
- `D` = Adverb (?)
- `RP.GS` = Relative Pronoun, Genitive, Singular
- `RD.GSM` = Relative/Demonstrative, Genitive, Singular, Masculine
- `RA.NSM` = Article, Nominative, Singular, Masculine
- `X` = Particle

**Key difference from RMAC**: LXX uses dot separator (`V.AAI3S`) while RMAC uses hyphen (`V-AAI-3S`).

**Impact on study.html**: The `renderLxxMorph` function (line 1110) is only used for hover display — it shows `w.g` (gloss) + lemma. It does NOT call `explainEnding` or `verbTenseEs`. The `openLxxStudy` popup (line 1131) shows raw morph code without human-readable explanation.

**Impact on unified_html**: LXX morphology is completely absent — `lxx_morphology` key is never used.

---

## 7. `gather_chapter_data` Candidates Handling for OT

**Function**: `get_all_db_names(book)` in `books.py:124-130`
- Returns `[canonical_name] + [all aliases]`
- For Psalms: `["Psalms", "Ps", "Pss", "Sal", "Salmos", ...]`

**DB name inconsistency** (confirmed):
- `morphology` table: uses abbreviations (`Ps`, `Gen`, `Exod`, `Isa`)
- `verses` table: mixed (`Ps` and `Psalms`)
- `patristic` table: uses full English names (`Psalms`, `Genesis`, `Isaiah`)
- `cross_refs` table: uses `source_book` field

**Verdict**: The `candidates` loop correctly handles this by trying all variants. Each query (`for b in candidates: rows = db.execute(..., (b, chapter,...))`) will find data regardless of which name format that particular table uses.

---

## 8. DB Word Count Consistency (WLC)

**Confirmed**: Zero mismatches. Every chapter with WLC morphology words has corresponding WLC verses, and vice versa. The sub-verse merging (9a, 13a → parent verse) works correctly.

---

## 9. Exegetical/Greek Commentaries for OT

**`commentaries` table**: NT-ONLY (27 books: Matthew through Revelation). Zero OT entries.
- Source: Robertson's Word Pictures, Vincent's Word Studies, etc. — all NT commentary.

**`greek_commentaries` in chapter_data**: Only populated when `data["morphology"]` exists (line 298). For OT, morphology exists (WLC), so the code attempts the query... but the `commentaries` table has no OT data.

**Result**: OT chapters get `data["greek_commentaries"] = {}` — the exegetical section never appears in study.html (because `commCount` = 0) and never appears in unified_html (because `commentaries` list is empty).

**Patristic fills some of this gap**: Genesis has 9,266 patristic entries, Psalms has 21,625. But these are Father citations, not word-level exegesis.

---

## 10. Improvements to Make Unified Analysis Equivalent for OT

### Priority 1 — Critical Rendering (unified_html_generator.py)
1. **Render WLC Hebrew line** with interactive morphology (RTL direction, Hebrew font)
2. **Render LXX line** with interactive morphology hover (using `lxx_morphology` data)
3. **Show LXX-ES translation** below LXX line
4. **Use separate color styling** for Hebrew vs Greek (current: all green Greek styling)

### Priority 2 — Morphology Intelligence (study_html_generator.py JS)
5. **Add `explainHebrewMorph(code)` function** that parses OSHM codes:
   - `H` prefix = Hebrew
   - Part of speech: N(oun), V(erb), P(reposition), C(onjunction), R(elative), T(article), A(djective)
   - Verb stems: q(al), n(iphal), p(iel), pu(al), h(ithpael), hi(phil), ho(phal)
   - Verb forms: p(erfect), i(mperfect), w(ayyiqtol/wayyiqtol), v(oluntative), c(ohortative), j(ussive), a(imperative), r(participle active), s(participle passive)
   - Person/gender/number
6. **Add `explainLxxMorph(code)` function** that parses dot-format LXX codes (similar to RMAC but with `.` instead of `-`)
7. **Add Hebrew `contextualMeaning` entries** for common verb forms

### Priority 3 — External Links Fix
8. **Fix `openWordStudy` links** for H-numbers:
   - BibleHub: `biblehub.com/hebrew/${num}.htm`
   - Replace Perseus/Logeion with Hebrew tools: Gesenius, BDB, HALOT online
   - Add link to Pealim (modern Hebrew verb conjugations for reference)
9. **Fix `openLxxStudy`** to include morphology explanation (currently just shows raw code)

### Priority 4 — Content Gap
10. **Add OT commentary sources** to `commentaries` table:
    - Keil & Delitzsch (public domain)
    - Matthew Henry (public domain)
    - Cambridge Bible Commentary (public domain, older editions)
    - This would enable the exegetical section for OT in both study.html and unified_analysis.html

### Priority 5 — Unified Analysis Parity
11. **Word decomposition for Hebrew**: Slash-separated morphemes (`בְּ/רֵאשִׁ֖ית` = preposition + noun) could be visualized like Greek compound decomposition
12. **Add verb root system display**: Show 3-letter root (שׁרשׁ) with binyan pattern for Hebrew verbs
