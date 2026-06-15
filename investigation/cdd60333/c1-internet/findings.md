# Internet Research Findings: OT Quality & Unified Analysis HTML Generator

## 1. Morphology Code Format Differences (CRITICAL BUG)

### Three Incompatible Morphology Systems

The study_html_generator.py uses `renderMorph` and `explainEnding`/`verbTenseEs` functions originally designed for **RMAC (Robinson's Morphological Analysis Codes)**. However, WLC and LXX use completely different formats:

| System | Format | Example | Used By |
|--------|--------|---------|---------|
| RMAC (Robinson) | `POS-TENSE_VOICE_MOOD-PERSON_NUMBER` dash-separated | `V-PAI-3S` (verb, present active indicative, 3rd singular) | MorphGNT (NT Greek) |
| OSHM (OpenScriptures) | `LANGUAGE + POS + type + person + gender + number + state` no separators | `HVqp3ms` (Hebrew verb, qal, perfect, 3rd masc sing) | WLC (Hebrew) |
| CATSS (LXX) | `TYPE PARSE` space-separated, type has declension | `V1 AAI3S` or dot-format `V.AAI3S` | LXX-Rahlfs-1935 |

### OSHM Code Structure (confirmed from hb.openscriptures.org)

Format: `[H|A][POS][details...]` where:
- First char: `H` (Hebrew) or `A` (Aramaic)
- Second char: Part of speech (`V`=verb, `N`=noun, `A`=adjective, `C`=conjunction, `D`=adverb, `P`=pronoun, `R`=preposition, `S`=suffix, `T`=particle)
- For verbs: `[stem][conjugation_type][person][gender][number][state]`
  - Stems: `q`=qal, `N`=niphal, `p`=piel, `P`=pual, `h`=hiphil, `H`=hophal, `t`=hithpael, etc.
  - Conjugation: `p`=perfect, `i`=imperfect, `w`=wayyiqtol, `v`=imperative, `r`=ptcp active, etc.
- For nouns: `[type][gender][number][state]`
  - Types: `c`=common, `p`=proper, `g`=gentilic
  - Gender: `m`=masc, `f`=fem, `b`=both, `c`=common
  - Number: `s`=singular, `p`=plural, `d`=dual
  - State: `a`=absolute, `c`=construct, `d`=determined

**Source**: https://hb.openscriptures.org/parsing/HebrewMorphologyCodes.html

### CATSS/LXX Code Structure

The CATSS system uses a two-part code: TYPE field + PARSE field:
- Type: `N1` (1st decl noun), `N2` (2nd decl), `V1` (regular present verb), `A1` (adjective), `RA` (article), etc.
- Parse: Case+Number+Gender for nouns (e.g., `NSM` = nominative singular masculine)
- Parse for verbs: Tense+Voice+Mood+Person+Number (e.g., `AAI3S` = aorist active indicative 3rd singular)

The LXX-Rahlfs-1935 dataset (eliranwong) integrates CATSS morphology. The format in the database may use dot notation (`N.NSM`, `V.AAI3S`) or the CATSS space format.

**Source**: http://ccat.sas.upenn.edu/gopher/text/religion/biblical/lxxmorph/*Morph-Coding

### Impact on study_html_generator.py

The `renderMorph` function expects RMAC dash-separated format (`V-PAI-3S`). When fed:
- `HVqp3ms` (OSHM Hebrew) → will NOT parse correctly, no dashes to split on
- `V.AAI3S` (CATSS LXX) → dot instead of dash, different position encoding

**Required Fix**: Implement three separate morphology parsers in JavaScript, detecting the format by:
1. Starts with `H` or `A` + no dots/dashes → OSHM Hebrew/Aramaic
2. Contains `.` → CATSS LXX format
3. Contains `-` → RMAC (NT Greek)

### Reference Implementation Found

A complete JavaScript implementation handling both Robinson AND OSHB formats exists at:
https://www.laparola.net/app/js/bible/morphology.js

This file contains:
- `bible.morphology['robinson'].format(morph)` — full RMAC parser
- `bible.morphology['OSHB'].format(morph)` — full Hebrew morphology parser with verb stems, conjugation types, noun types, etc.

**This is the exact pattern the study_html_generator.py should follow.**

## 2. Hebrew Strong's Numbers and Word Study Links

### Strong's Number Format in morphhb

The OpenScriptures morphhb uses **numeric-only** lemma values:
- `lemma="430"` for אֱלֹהִים (elohim) → displayed as H430
- `lemma="7225"` for רֵאשִׁית (reshit) → displayed as H7225
- `lemma="1254 a"` for בָּרָא (bara) → H1254 (with variant letter suffix)

The `H` prefix is a display convention, not stored in the data.

### Correct External Link URLs for Hebrew Strong's

- **Blue Letter Bible**: `https://www.blueletterbible.org/lexicon/h{number}/kjv/wlc/0-1/`
  - Example: https://www.blueletterbible.org/lexicon/h7225/kjv/wlc/0-1/
- **BibleHub**: `https://biblehub.com/hebrew/{number}.htm`

### Impact on openWordStudy

If the `openWordStudy` function builds links using `G` prefix logic (for Greek Strong's), it needs a parallel path for `H` prefix numbers. The URL structures differ between Greek and Hebrew on Blue Letter Bible:
- Greek: `/lexicon/g{number}/kjv/tr/0-1/`
- Hebrew: `/lexicon/h{number}/kjv/wlc/0-1/`

## 3. Hebrew Word Compound Splits (slash notation)

### The slash separator issue

morphhb represents Hebrew words with prefixes separated by `/`:
```xml
<w lemma="b/7225" morph="HR/Ncfsa">בְּ/רֵאשִׁ֖ית</w>
<w lemma="d/8064" morph="HTd/Ncmpa">הַ/שָּׁמַ֖יִם</w>
<w lemma="c/853" morph="HC/To">וְ/אֵ֥ת</w>
```

**Key rule from openscriptures.org**: "The number of morphological parts must match the number of word parts (i.e. they should both have the same number of slashes)"

### Impact on word count

This means a single orthographic word like "בְּרֵאשִׁ֖ית" may have 2 morphological entries in the DB:
1. `HR` (preposition prefix "be-")
2. `Ncfsa` (noun common feminine singular absolute "reshit")

**If the ingest stored these as separate word_pos entries**, the word count per verse in morphology_words table will NOT match the whitespace-delimited word count in the verses table. This is expected and correct for morphological analysis, but the display logic needs to handle compound words.

### Display recommendation

When rendering, compound parts (those sharing the same orthographic word) should be displayed together with a visual separator, showing the morphology of each prefix/suffix separately in the tooltip.

## 4. LXX Book Naming Variants (candidates list issue)

### LXX uses different book names than Hebrew/English

| English/Hebrew | LXX/Greek Name |
|---------------|----------------|
| 1 Samuel | 1 Kingdoms (Βασιλειῶν Αʹ) |
| 2 Samuel | 2 Kingdoms (Βασιλειῶν Βʹ) |
| 1 Kings | 3 Kingdoms (Βασιλειῶν Γʹ) |
| 2 Kings | 4 Kingdoms (Βασιλειῶν Δʹ) |
| 1 Chronicles | 1 Paralipomenon |
| 2 Chronicles | 2 Paralipomenon |
| Ezra | 2 Esdras (first part) |
| Nehemiah | 2 Esdras (second part) |

**Source**: https://en.wikipedia.org/wiki/Books_of_the_Kingdoms

### Impact on gather_chapter_data

The `candidates` list for book name matching needs to include these LXX variants. If the LXX data in bible.db uses "1Kingdoms" or "1Reigns" as the book name, and the lookup uses "1Samuel", the query will miss the LXX data entirely.

## 5. Psalm Versification Differences

### The LXX Psalm numbering offset

| Hebrew/English | LXX/Vulgate |
|---------------|-------------|
| Psalms 1-8 | Same |
| Psalms 9-10 (Hebrew) | Psalm 9 (LXX, combined) |
| Psalms 10-113 (Hebrew) | Psalms 9-112 (LXX, offset by -1) |
| Psalm 114-115 (Hebrew) | Psalm 113 (LXX, combined) |
| Psalm 116 (Hebrew) | Psalms 114-115 (LXX, split) |
| Psalms 117-146 (Hebrew) | Psalms 116-145 (LXX, offset by -1) |
| Psalm 147 (Hebrew) | Psalms 146-147 (LXX, split) |
| Psalms 148-150 | Same |
| — | Psalm 151 (LXX only) |

**Source**: https://taylormarshall.com/2010/03/how-to-untangle-numbering-of-psalms.html

### Impact

The versification normalization in the project README mentions this, but the LXX morphology data will use LXX numbering. When displaying parallel versions for Psalms, the word-by-word morphology for LXX needs the offset applied.

## 6. Patristic Commentary Coverage for OT

### ANF/NPNF OT Content (confirmed)

The Ante-Nicene and Nicene/Post-Nicene Fathers DO contain extensive OT commentary:
- **Chrysostom**: 67 Homilies on Genesis (full coverage Gen 1-50)
- **Augustine**: Commentary on Genesis (first 3 chapters), full Commentary on Psalms
- **Origen**: Homilies on Genesis, Exodus, Leviticus, Numbers, Joshua, Judges, Isaiah, Jeremiah, Ezekiel, Song of Songs
- **Jerome**: 59 Homilies on Psalms, Commentary on Isaiah, Jeremiah, Ezekiel, Daniel, Minor Prophets
- **Basil**: Hexaemeron (Genesis creation)
- **Gregory of Nyssa**: On the Life of Moses

**Source**: https://archive.sacred-texts.com/chr/ecf/106/1060003.htm (NPNF Vol. VI index)

### Impact on commentaries table

The data IS available in the gregorycrane/nicenefathers TEI XML source. The question is whether `ingest/index_patristic_llm.py` successfully:
1. Parsed the TEI XML for OT book references
2. Matched patristic passages to OT verse references
3. Indexed with correct book names (Greek fathers use LXX naming!)

If the indexing used NT-centric regex patterns for verse references, OT passages may have been missed.

### Additional source found

**HistoricalChristianFaith/Commentaries-Database** on GitHub: A pre-organized collection of commentaries by author/verse that could supplement the ANF/NPNF data.

## 7. RTL Display for Hebrew Text

### Best practices for Hebrew word-by-word display

1. Container: `dir="rtl"` attribute on the Hebrew text container
2. Word wrapping: Use `display: flex; flex-wrap: wrap; flex-direction: row-reverse;` for word-level flex items
3. Tooltip positioning: Must account for RTL - tooltip anchored to the right side of words
4. Mixed content: When showing Hebrew + transliteration + translation in tooltip, use `unicode-bidi: embed` on inline LTR elements within RTL context
5. Brackets and punctuation: Add `&rlm;` (right-to-left mark) after closing brackets to prevent reversal

**Sources**: MDN CSS direction docs, Stack Overflow RTL best practices

## 8. Feature Gap: NT vs OT in study.html

Based on the investigation context and web research, the likely gaps for OT chapters:

### NT chapters get:
1. ✅ MorphGNT word-by-word morphology with RMAC parsing
2. ✅ Greek text with hover showing full grammatical breakdown
3. ✅ `explainEnding` / `verbTenseEs` human-readable explanations
4. ✅ Greek Strong's (G numbers) with correct BLB links
5. ✅ Patristic commentary (well-indexed for NT verses)
6. ✅ Greek commentaries field
7. ✅ Critical apparatus (textual variants)

### OT chapters likely get (with bugs):
1. ⚠️ WLC word-by-word morphology — data present but OSHM codes NOT parsed by renderMorph
2. ⚠️ Hebrew text display — RTL may have CSS issues
3. ❌ `explainEnding` will fail — expects RMAC format, gets `HVqp3ms`
4. ⚠️ Hebrew Strong's (H numbers) — links may use wrong URL format
5. ⚠️ Patristic commentary — may be sparse if indexing missed OT refs
6. ⚠️ LXX parallel text with morphology — CATSS codes NOT parsed by renderMorph
7. ⚠️ LXX-ES translation — needs to be integrated into display
8. ❌ No critical apparatus for OT (table may only have NT variants)

## 9. Recommendations for Making Unified Analysis Equivalent for OT

### Priority 1 (Critical bugs):
1. **Implement OSHM morphology parser in JS** — use the laparola.net reference implementation pattern
2. **Implement CATSS/LXX morphology parser in JS** — detect format by presence of dots vs dashes
3. **Fix openWordStudy for Hebrew** — correct URL patterns for H-number lookups
4. **Handle compound words** (slash-separated morphology parts) in display

### Priority 2 (Feature parity):
5. **Add Hebrew verb explanation function** — equivalent to `verbTenseEs` but for Hebrew stems/conjugations
6. **Add LXX-ES translation display** — show Spanish literal translation alongside LXX Greek
7. **Verify patristic indexing for OT** — check commentaries table coverage for Genesis, Psalms, Isaiah
8. **RTL CSS fixes** — ensure Hebrew text container uses proper `dir=rtl` with flex layout

### Priority 3 (Enhancement):
9. **Book name variant mapping** — ensure candidates list includes LXX naming variants
10. **Versification offset for LXX Psalms** — apply psalm number conversion when showing LXX parallel
11. **Critical apparatus for OT** — if data exists, integrate; otherwise note limitation
12. **Unified_html_generator parity** — port all OT fixes from study_html_generator.py

## Sources

1. OpenScriptures Hebrew Morphology Codes: https://hb.openscriptures.org/parsing/HebrewMorphologyCodes.html
2. CATSS LXX Morphology Coding: http://ccat.sas.upenn.edu/gopher/text/religion/biblical/lxxmorph/*Morph-Coding
3. LaParola JS Morphology Parser (RMAC + OSHB): https://www.laparola.net/app/js/bible/morphology.js
4. eliranwong/LXX-Rahlfs-1935: https://github.com/eliranwong/LXX-Rahlfs-1935
5. morphhb parsing rules: https://hb.openscriptures.org/parsing/
6. Blue Letter Bible Hebrew lexicon URL: https://www.blueletterbible.org/lexicon/h5927/kjv/wlc/0-1/
7. Books of the Kingdoms (Wikipedia): https://en.wikipedia.org/wiki/Books_of_the_Kingdoms
8. Psalm numbering differences: https://taylormarshall.com/2010/03/how-to-untangle-numbering-of-psalms.html
9. NPNF Index (sacred-texts): https://archive.sacred-texts.com/chr/ecf/106/1060003.htm
10. byztxt/robinson-documentation: https://github.com/byztxt/robinson-documentation
