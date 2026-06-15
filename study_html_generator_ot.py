"""Generate interactive chapter study HTML with popups, word definitions, and cross-ref previews."""
import json, sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "bible.db"
S3_BUCKET = "bible-study-cache-609009159737"


def _s3_cache_get(key: str) -> str:
    """Get cached content from S3. Returns empty string if not found."""
    import boto3
    from botocore.config import Config
    try:
        client = boto3.client("s3", region_name="us-east-1", config=Config(connect_timeout=5, read_timeout=10))
        obj = client.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return ""


def _s3_cache_put(key: str, content: str):
    """Store content in S3 cache."""
    import boto3
    from botocore.config import Config
    try:
        client = boto3.client("s3", region_name="us-east-1", config=Config(connect_timeout=5, read_timeout=10))
        client.put_object(Bucket=S3_BUCKET, Key=key, Body=content.encode("utf-8"), ContentType="text/html")
    except Exception:
        pass


def _get_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def gather_chapter_data(book: str, chapter: int, version: str, candidates: list) -> dict:
    """Gather all data needed for the interactive HTML."""
    db = _get_db()
    data = {"book": book, "chapter": chapter, "version": version, "verses": [], "parallel": {},
            "patristic": [], "xrefs": [], "apparatus": [], "morphology": {}, "rmac": {}}

    # Verses in requested version
    for b in candidates:
        rows = db.execute("SELECT verse_num, text FROM verses WHERE book=? AND chapter=? AND version=? ORDER BY verse_num", (b, chapter, version)).fetchall()
        if rows:
            data["verses"] = [{"v": r["verse_num"], "text": r["text"]} for r in rows]
            break

    # Ensure we have Spanish translation for NT toggle (separate from main version)
    if version != "RVR60":
        for b in candidates:
            rows = db.execute("SELECT verse_num, text FROM verses WHERE book=? AND chapter=? AND version='RVR60' ORDER BY verse_num", (b, chapter)).fetchall()
            if not rows:
                rows = db.execute("SELECT verse_num, text FROM verses WHERE book=? AND chapter=? AND version='RVR1909' ORDER BY verse_num", (b, chapter)).fetchall()
            if rows:
                data["spanish"] = {r["verse_num"]: r["text"] for r in rows}
                break

    # Parallel versions (original + LXX)
    for ver in ["WLC", "LXX"]:
        for b in candidates:
            rows = db.execute("SELECT verse_num, text FROM verses WHERE book=? AND chapter=? AND version=? ORDER BY verse_num", (b, chapter, ver)).fetchall()
            if rows:
                data["parallel"][ver] = {r["verse_num"]: r["text"] for r in rows}
                break

    # All translations for verse comparison
    data["translations"] = {}
    for ver in ["RVR60", "RVR1909", "KJV", "ASV", "BSB", "Darby", "LITV", "YLT", "Vulgate"]:
        for b in candidates:
            rows = db.execute("SELECT verse_num, text FROM verses WHERE book=? AND chapter=? AND version=? ORDER BY verse_num", (b, chapter, ver)).fetchall()
            if rows:
                data["translations"][ver] = {r["verse_num"]: r["text"] for r in rows}
                break

    # Morphology (word-level) - with lexicon lookup
    for b in candidates:
        rows = db.execute("""
            SELECT verse_num, word_pos, word, lemma, morph_code, gloss, strongs, gloss_es
            FROM morphology WHERE book=? AND chapter=? AND version='MorphGNT'
            ORDER BY verse_num, word_pos
        """, (b, chapter)).fetchall()
        if not rows:
            rows = db.execute("""
                SELECT verse_num, word_pos, word, lemma, morph_code, gloss, strongs, '' as gloss_es
                FROM morphology WHERE book=? AND chapter=? AND version='WLC'
                ORDER BY verse_num, word_pos
            """, (b, chapter)).fetchall()
        if rows:
            # Build lexicon lookup for all lemmas in this chapter
            lemmas = list(set(r["lemma"] for r in rows if r["lemma"]))
            lex_map = {}
            if lemmas:
                import unicodedata, re as _re
                # Load all lexicon entries into a normalized lookup
                all_lex = db.execute("SELECT strongs, lemma, lemma_normalized, gloss, definition FROM lexicon").fetchall()
                norm_lex = {}
                stripped_lex = {}
                for lx in all_lex:
                    # Key by Strong's number (for WLC Hebrew lookup)
                    if lx["strongs"]:
                        norm_lex[lx["strongs"]] = lx
                    # Key by NFC-normalized lemma (handles tonos vs oxia)
                    nfc = unicodedata.normalize('NFC', lx["lemma"])
                    norm_lex[nfc] = lx
                    norm_lex[lx["lemma"]] = lx
                    if lx["lemma_normalized"]:
                        norm_lex[unicodedata.normalize('NFC', lx["lemma_normalized"])] = lx
                    # Key by fully stripped (no diacritics) for fallback
                    stripped = ''.join(c for c in unicodedata.normalize('NFD', lx["lemma"]) if unicodedata.category(c) != 'Mn').lower()
                    stripped_lex[stripped] = lx

                for lem in lemmas:
                    # Strip trailing punctuation and parenthetical
                    clean = _re.sub(r'[,.\;·]$', '', lem)
                    clean = _re.sub(r'\(.\)$', '', clean)  # γέγονε(ν) → γέγονε
                    # Try NFC-normalized exact match
                    nfc_clean = unicodedata.normalize('NFC', clean)
                    if nfc_clean in norm_lex:
                        lx = norm_lex[nfc_clean]
                        lex_map[lem] = {"s": lx["strongs"], "g": lx["gloss"] or "", "d": lx["definition"] or "", "lemma_text": lx["lemma"]}
                        continue
                    # Try stripped (no diacritics) match
                    stripped = ''.join(c for c in unicodedata.normalize('NFD', clean) if unicodedata.category(c) != 'Mn').lower()
                    if stripped in stripped_lex:
                        lx = stripped_lex[stripped]
                        lex_map[lem] = {"s": lx["strongs"], "g": lx["gloss"] or "", "d": lx["definition"] or "", "lemma_text": lx["lemma"]}
                        continue
                    # Stem match: try removing last 1-5 chars (Greek inflection)
                    for trim in range(1, 6):
                        if len(stripped) <= trim + 2:
                            break
                        stem = stripped[:-trim]
                        matches = [v for k, v in stripped_lex.items() if k.startswith(stem) and len(k) <= len(stripped) + 3]
                        if matches:
                            lx = matches[0]
                            lex_map[lem] = {"s": lx["strongs"], "g": lx["gloss"] or "", "d": lx["definition"] or "", "lemma_text": lx["lemma"]}
                            break

            for r in rows:
                vn = r["verse_num"]
                lex = lex_map.get(r["lemma"], {})
                # Also try by strongs field
                if not lex and r["strongs"]:
                    lex = lex_map.get(r["strongs"], {})
                # Fallback: check lemma_gloss table for LLM-generated glosses
                if not lex.get("g"):
                    try:
                        lg = db.execute("SELECT gloss FROM lemma_gloss WHERE lemma=?", (r["lemma"],)).fetchone()
                        if lg:
                            lex = {"g": lg["gloss"], "s": "", "d": ""}
                    except Exception:
                        pass
                data["morphology"].setdefault(vn, []).append({
                    "w": r["word"], "l": lex.get("lemma_text", r["lemma"]),
                    "m": r["morph_code"] or "",
                    "g": r["gloss"] or lex.get("g", ""), "s": r["strongs"] or lex.get("s", ""),
                    "d": lex.get("d", ""), "es": r["gloss_es"] or ""
                })
            break

    # LXX morphology (separate from main, for OT parallel display)
    if "WLC" in data["parallel"] or not data["morphology"]:
        for b in candidates:
            lxx_rows = db.execute("""
                SELECT verse_num, word_pos, word, lemma, morph_code, gloss, strongs, '' as gloss_es
                FROM morphology WHERE book=? AND chapter=? AND version='LXX'
                ORDER BY verse_num, word_pos
            """, (b, chapter)).fetchall()
            if lxx_rows:
                data["lxx_morphology"] = {}
                for r in lxx_rows:
                    vn = r["verse_num"]
                    data["lxx_morphology"].setdefault(vn, []).append({
                        "w": r["word"], "l": r["lemma"], "m": r["morph_code"] or "",
                        "g": r["gloss"] or "", "s": r["strongs"] or "", "d": "", "es": ""
                    })
                break

    # LXX literal translation to Spanish (cached in S3)
    if "LXX" in data["parallel"]:
        # Use morphology words for full text (includes sub-verses like 9a)
        if data.get("lxx_morphology"):
            lxx_full = {v: " ".join(w["w"] for w in words) for v, words in data["lxx_morphology"].items()}
        else:
            lxx_full = data["parallel"]["LXX"]
        data["lxx_spanish"] = _translate_lxx(book, chapter, lxx_full)

    # RMAC parsing descriptions
    try:
        rmac_rows = db.execute("SELECT code, description FROM rmac_codes").fetchall()
        data["rmac"] = {r["code"]: r["description"] for r in rmac_rows}
    except Exception:
        pass

    # Compound word decomposition
    data["compounds"] = {}
    try:
        # Get all unique lemmas in this chapter's morphology
        all_lemmas = set()
        for vwords in data["morphology"].values():
            for w in vwords:
                all_lemmas.add(w["l"])
        if all_lemmas:
            placeholders = ",".join("?" * len(all_lemmas))
            comp_rows = db.execute(f"SELECT lemma, components, meaning_es, root_note_es FROM compounds WHERE lemma IN ({placeholders})", list(all_lemmas)).fetchall()
            for r in comp_rows:
                data["compounds"][r["lemma"]] = {
                    "parts": json.loads(r["components"]),
                    "meaning": r["meaning_es"] or "",
                    "root_note": r["root_note_es"] or ""
                }
            # Also load word_morphology decomposition
            try:
                wm_rows = db.execute(f"SELECT lemma, prefix_greek, prefix_meaning, root_greek, root_meaning, suffix_greek, suffix_function, ending_greek, ending_function FROM word_morphology WHERE lemma IN ({placeholders})", list(all_lemmas)).fetchall()
                for r in wm_rows:
                    if r["lemma"] not in data["compounds"]:
                        parts = []
                        if r["prefix_greek"]:
                            parts.append({"greek": r["prefix_greek"], "meaning_es": r["prefix_meaning"], "type": "prefijo"})
                        if r["root_greek"]:
                            parts.append({"greek": r["root_greek"], "meaning_es": r["root_meaning"], "type": "raíz"})
                        if r["suffix_greek"]:
                            parts.append({"greek": r["suffix_greek"], "meaning_es": r["suffix_function"], "type": "sufijo"})
                        if r["ending_greek"]:
                            parts.append({"greek": r["ending_greek"], "meaning_es": r["ending_function"], "type": "desinencia"})
                        if parts:
                            data["compounds"][r["lemma"]] = {"parts": parts, "meaning": "", "root_note": ""}
            except Exception:
                pass
    except Exception:
        pass

    # Patristic (deduplicated, non-empty)
    for b in candidates:
        rows = db.execute("""
            SELECT DISTINCT verse_num, father, work, text, original_lang, text_original
            FROM patristic WHERE book=? AND chapter=? AND (length(text) > 30 OR length(text_original) > 30)
            ORDER BY verse_num, father
        """, (b, chapter)).fetchall()
        if rows:
            data["patristic"] = [{"v": r["verse_num"], "f": r["father"], "w": r["work"] or "",
                                  "t": r["text"], "lang": r["original_lang"] or "",
                                  "orig": r["text_original"] or ""} for r in rows]
            break

    # Cross-references with target text
    for b in candidates:
        rows = db.execute("SELECT DISTINCT source_verse, target_ref, relationship, notes FROM cross_refs WHERE source_book=? AND source_chapter=? ORDER BY source_verse, target_ref", (b, chapter)).fetchall()
        if rows:
            # Limit to 8 refs per verse to ensure coverage across all verses
            per_verse = {}
            for r in rows:
                v = r["source_verse"]
                per_verse.setdefault(v, [])
                if len(per_verse[v]) < 8:
                    ref_text = _lookup_ref_text(db, r["target_ref"])
                    per_verse[v].append({"v": v, "ref": r["target_ref"],
                                         "rel": r["relationship"] or "", "text": ref_text})
            for v in sorted(per_verse):
                data["xrefs"].extend(per_verse[v])
            break

    # Apparatus
    for b in candidates:
        rows = db.execute("SELECT verse_num, variant_id, reading, manuscripts, text_type, notes FROM apparatus WHERE book=? AND chapter=? ORDER BY verse_num", (b, chapter)).fetchall()
        if rows:
            data["apparatus"] = [{"v": r["verse_num"], "vid": r["variant_id"], "r": r["reading"],
                                  "ms": r["manuscripts"] or "", "tt": r["text_type"] or "", "n": r["notes"] or ""} for r in rows]
            break

    # Generate textual criticism analysis if there are variants
    if data["apparatus"]:
        data["tc_analysis"] = _generate_tc_analysis(book, chapter, data["apparatus"], data["verses"])

    # Load manuscript details for apparatus
    data["manuscripts"] = {}
    try:
        ms_rows = db.execute("SELECT sigla, name, date_text, date_approx, origin, origin_lat, origin_lng, discovery_place, discovery_lat, discovery_lng, discovery_date, content, text_type, current_location, description, reliability, validators FROM manuscripts").fetchall()
        for r in ms_rows:
            data["manuscripts"][r["sigla"]] = {
                "name": r["name"], "date": r["date_text"], "year": r["date_approx"],
                "origin": r["origin"], "olat": r["origin_lat"], "olng": r["origin_lng"],
                "disc_place": r["discovery_place"], "dlat": r["discovery_lat"], "dlng": r["discovery_lng"],
                "disc_date": r["discovery_date"], "content": r["content"], "type": r["text_type"],
                "location": r["current_location"], "desc": r["description"],
                "reliability": r["reliability"], "validators": r["validators"]
            }
    except Exception:
        pass

    # Generate exegetical commentary from the Greek
    if data["morphology"]:
        # Load real commentaries (Robertson, Vincent, etc.) - NO LLM needed
        data["greek_commentaries"] = {}
        try:
            comm_rows = db.execute("""SELECT verse_num, source, source_name, text
                FROM commentaries WHERE book=? AND chapter=?
                ORDER BY verse_num, source""", (book, chapter)).fetchall()
            for r in comm_rows:
                data["greek_commentaries"].setdefault(r["verse_num"], []).append({
                    "src": r["source"], "name": r["source_name"], "text": r["text"]
                })
        except Exception:
            pass
        data["exegetical"] = ""

    db.close()
    return data


def _lookup_ref_text(db, ref: str) -> dict:
    """Get cross-reference target text in 4 languages: es, gr (WLC/MorphGNT), lxx, en."""
    import re
    m = re.match(r'(.+?)\s+(\d+):(\d+)', ref)
    if not m:
        return {"es": "", "gr": "", "lxx": "", "en": ""}
    book_raw, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
    # Map full names to DB abbreviations
    NAME_TO_DB = {
        'Genesis':'Gen','Exodus':'Exod','Leviticus':'Lev','Numbers':'Num','Deuteronomy':'Deut',
        'Joshua':'Josh','Judges':'Judg','Ruth':'Ruth','1 Samuel':'1Sam','2 Samuel':'2Sam',
        '1 Kings':'1Kgs','2 Kings':'2Kgs','1 Chronicles':'1Chr','2 Chronicles':'2Chr',
        'Ezra':'Ezra','Nehemiah':'Neh','Esther':'Esth','Job':'Job','Psalms':'Ps',
        'Proverbs':'Prov','Ecclesiastes':'Eccl','Song of Solomon':'Song',
        'Isaiah':'Isa','Jeremiah':'Jer','Lamentations':'Lam','Ezekiel':'Ezek',
        'Daniel':'Dan','Hosea':'Hos','Joel':'Joel','Amos':'Amos','Obadiah':'Obad',
        'Jonah':'Jonah','Micah':'Mic','Nahum':'Nah','Habakkuk':'Hab',
        'Zephaniah':'Zeph','Haggai':'Hag','Zechariah':'Zech','Malachi':'Mal',
        'Matthew':'Matthew','Mark':'Mark','Luke':'Luke','John':'John','Acts':'Acts',
        'Romans':'Romans','1 Corinthians':'1 Corinthians','2 Corinthians':'2 Corinthians',
        'Galatians':'Galatians','Ephesians':'Ephesians','Philippians':'Philippians',
        'Colossians':'Colossians','1 Thessalonians':'1 Thessalonians','2 Thessalonians':'2 Thessalonians',
        '1 Timothy':'1 Timothy','2 Timothy':'2 Timothy','Titus':'Titus','Philemon':'Philemon',
        'Hebrews':'Hebrews','James':'James','1 Peter':'1 Peter','2 Peter':'2 Peter',
        '1 John':'1 John','2 John':'2 John','3 John':'3 John','Jude':'Jude','Revelation':'Revelation',
    }
    book = NAME_TO_DB.get(book_raw, book_raw)
    # Also try the raw name and common abbreviations as candidates
    candidates = [book, book_raw]
    if book != book_raw:
        candidates.append(book_raw)

    OT_ABBREVS = {'Gen','Exod','Lev','Num','Deut','Josh','Judg','Ruth','1Sam','2Sam',
                  '1Kgs','2Kgs','1Chr','2Chr','Ezra','Neh','Esth','Job','Ps','Prov',
                  'Eccl','Song','Isa','Jer','Lam','Ezek','Dan','Hos','Joel','Amos',
                  'Obad','Jonah','Mic','Nah','Hab','Zeph','Hag','Zech','Mal'}
    is_ot = book in OT_ABBREVS

    def qv(ver):
        for b in candidates:
            row = db.execute("SELECT text FROM verses WHERE book=? AND chapter=? AND verse_num=? AND version=? LIMIT 1", (b, ch, vs, ver)).fetchone()
            if row:
                return row["text"][:300]
        return ""

    result = {"es": "", "gr": "", "lxx": "", "en": ""}
    result["es"] = qv("RVR1909") or qv("RVR60")
    result["en"] = qv("KJV") or qv("BSB")
    if is_ot:
        result["gr"] = qv("WLC")
        result["lxx"] = qv("LXX")
    else:
        result["gr"] = qv("MorphGNT") or qv("SBLGNT")
        result["lxx"] = ""
    return result


def _strip_md(text: str) -> str:
    """Strip markdown code fences from LLM HTML output."""
    import re
    return re.sub(r'^```\w*\n?|```$', '', text.strip()).strip()


def _translate_lxx(book: str, chapter: int, lxx_verses: dict) -> dict:
    """Translate LXX Greek to literal Spanish using Claude Opus. Returns {verse_num: text}."""
    cache_key = f"cache/{book}/{chapter}/lxx_spanish.json"
    cached = _s3_cache_get(cache_key)
    if cached:
        import json
        return json.loads(cached)
    import boto3, json
    lxx_text = "\n".join(f"{v}. {t}" for v, t in sorted(lxx_verses.items()))
    prompt = f"""Traduce el siguiente texto griego de la Septuaginta (LXX) al español de forma LITERAL, lo más cercano posible palabra por palabra.

Reglas:
- Traducción LITERAL palabra por palabra, preservando el orden griego cuando sea posible
- Si el orden griego es ininteligible en español, haz el mínimo ajuste necesario
- NO parafrasees, NO interpretes, NO suavices
- Mantén artículos, conjunciones, pronombres tal como aparecen en el griego
- Usa "pero" para δέ, "y" para καί, "pues/porque" para γάρ
- Mantén la numeración
- Un versículo por línea, formato: "N. texto"

TEXTO GRIEGO ({book} {chapter}, LXX):
{lxx_text}"""
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        resp = client.converse(
            modelId="global.anthropic.claude-opus-4-8",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 4096}
        )
        text = resp["output"]["message"]["content"][0]["text"]
        result = {}
        for line in text.strip().split('\n'):
            line = line.strip()
            if line and line[0].isdigit():
                parts = line.split('.', 1)
                if len(parts) == 2:
                    try:
                        result[int(parts[0].strip())] = parts[1].strip()
                    except ValueError:
                        pass
        if result:
            _s3_cache_put(cache_key, json.dumps(result, ensure_ascii=False))
        return result
    except Exception:
        return {}


def _generate_tc_analysis(book: str, chapter: int, apparatus: list, verses: list) -> str:
    """Use LLM to generate textual criticism analysis."""
    cache_key = f"cache/{book}/{chapter}/tc_analysis.html"
    cached = _s3_cache_get(cache_key)
    if cached:
        return cached
    import boto3
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        variants_text = "\n".join(
            f"v.{a['v']} #{a['vid']}: {a['r']} — MSS: {a['ms']} ({a['tt']})"
            for a in apparatus
        )
        prompt = f"""Genera HTML para un an\u00e1lisis de cr\u00edtica textual de {book} {chapter}. SOLO HTML con estilos inline. Sin markdown.

VARIANTES:
{variants_text}

ESTRUCTURA REQUERIDA:

1. TABLA DE COLACI\u00d3N:
Filas = manuscritos. Columnas = posiciones SEM\u00c1NTICAS alineadas.
Las columnas se alinean por SIGNIFICADO, no por orden secuencial. Las palabras equivalentes van en la MISMA columna aunque una tradici\u00f3n tenga palabras extra.

Para Juan 1:18 la tabla CORRECTA es:

<div style="overflow-x:auto">
<table style="border-collapse:collapse;font-family:'Courier New',monospace;font-size:14px;white-space:nowrap">
<tr style="background:#1a237e;color:white">
  <th style="padding:8px 12px;border:1px solid #444;position:sticky;left:0;background:#1a237e;z-index:1">MS</th>
  <th style="padding:8px 12px;border:1px solid #444">1</th>
  <th style="padding:8px 12px;border:1px solid #444">2</th>
  <th style="padding:8px 12px;border:1px solid #444">3</th>
  <th style="padding:8px 12px;border:1px solid #444">4</th>
</tr>
<tr>
  <td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;position:sticky;left:0;background:#f5f5f5">P75, \u2135, B</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#eee"></td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#c8e6c9">\u03bc\u03bf\u03bd\u03bf\u03b3\u03b5\u03bd\u1f74\u03c2</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#c8e6c9">\u03b8\u03b5\u03cc\u03c2</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#c8e6c9">\u1f41 \u1f64\u03bd</td>
</tr>
<tr>
  <td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;position:sticky;left:0;background:#f5f5f5">A, Byz, TR</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#ffe0b2">\u1f41</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#ffe0b2">\u03bc\u03bf\u03bd\u03bf\u03b3\u03b5\u03bd\u1f74\u03c2</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#ffe0b2">\u03c5\u1f31\u03cc\u03c2</td>
  <td style="padding:8px 12px;border:1px solid #ddd;background:#ffe0b2">\u1f41 \u1f64\u03bd</td>
</tr>
</table>
</div>

REGLAS CR\u00cdTICAS:
- \u03b8\u03b5\u03cc\u03c2 y \u03c5\u1f31\u03cc\u03c2 van en la MISMA columna (son la variante, ocupan la misma posici\u00f3n sem\u00e1ntica)
- \u03bc\u03bf\u03bd\u03bf\u03b3\u03b5\u03bd\u1f74\u03c2 va en la misma columna para todos (todos lo tienen)
- Si un MS tiene \u1f41 extra que otros no tienen, esa celda queda vac\u00eda en los que no lo tienen
- Verde (#c8e6c9) = lectura preferida (NA28)
- Naranja (#ffe0b2) = lectura alternativa
- Gris (#eee) = celda vac\u00eda (el MS no tiene palabra ah\u00ed)

2. VEREDICTO: Cu\u00e1l lectura es original, por qu\u00e9, barra de confianza visual.

3. MANUSCRITOS: tabla con Sigla | Fecha | Origen | Link externo real.

4. IMPACTO TEOL\u00d3GICO: qu\u00e9 cambia doctrinalmente.

5. CRITERIOS como pills coloreados.

Responde en espa\u00f1ol. SOLO HTML."""

        r = client.converse(
            modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 5000, "temperature": 0},
        )
        result = _strip_md(r['output']['message']['content'][0]['text'])
        _s3_cache_put(cache_key, result)
        return result
    except Exception:
        return ""


def _generate_patristic_analysis(book: str, chapter: int, patristic: list) -> str:
    """Generate thematic analysis of patristic commentaries using multiple LLM calls."""
    cache_key = f"cache/{book}/{chapter}/patristic_analysis_v2.html"
    cached = _s3_cache_get(cache_key)
    if cached:
        return cached
    import boto3
    from botocore.config import Config
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1",
                              config=Config(read_timeout=180))

        # Split into chunks by verse groups
        from collections import defaultdict
        by_verse = defaultdict(list)
        for p in patristic:
            by_verse[p['v']].append(p)
        verses_sorted = sorted(by_verse.keys())

        # Create chunks of ~100 entries each
        chunks = []
        current_chunk = []
        for v in verses_sorted:
            current_chunk.extend(by_verse[v])
            if len(current_chunk) >= 100:
                chunks.append(current_chunk)
                current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        # Phase 1: Extract themes from each chunk
        chunk_analyses = []
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _call_chunk_phase1(i, chunk):
            texts = "\n".join(f"[v.{p['v']}] {p['f']}: {p['t'][:250]}" for p in chunk)
            verse_range = f"v.{chunk[0]['v']}-{chunk[-1]['v']}"
            prompt = f"""Analiza estos {len(chunk)} comentarios patrísticos de {book} {chapter} ({verse_range}).

COMENTARIOS:
{texts}

Extrae los TEMAS TEOLÓGICOS principales. Para cada tema devuelve JSON:
[{{"tema": "nombre", "padres_favor": [{{"padre": "X", "cita": "texto breve", "verso": N}}], "padres_contra": [{{"padre": "Y", "cita": "texto breve", "verso": N}}], "consenso": "alto|medio|bajo"}}]

SOLO JSON, sin explicación."""
            r = client.converse(
                modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 4000, "temperature": 0},
            )
            return (i, r['output']['message']['content'][0]['text'])

        # Phase 1: parallel (2 workers to avoid throttling)
        chunk_analyses = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(_call_chunk_phase1, i, chunk) for i, chunk in enumerate(chunks)]
            for f in as_completed(futures):
                try:
                    i, result = f.result()
                    chunk_analyses[i] = result
                except Exception:
                    pass

        # Phase 2: Expand each chunk's themes into detailed HTML with all citations
        def _call_chunk_phase2(i, analysis):
            verse_range = f"v.{chunks[i][0]['v']}-{chunks[i][-1]['v']}"
            full_texts = "\n".join(f"[v.{p['v']}] {p['f']} ({p['w']}): {p['t'][:400]}" for p in chunks[i])

            expand_prompt = f"""Genera HTML detallado para los temas patrísticos de {book} {chapter} ({verse_range}).

TEMAS IDENTIFICADOS:
{analysis}

TEXTOS COMPLETOS DE LOS PADRES:
{full_texts}

Para CADA tema genera HTML (estilos inline) con:
1. <h3> con nombre del tema
2. Barra de consenso (div con background verde/naranja/rojo)
3. Para CADA padre que opina sobre este tema:
   - Nombre del padre en negrita
   - Cita textual COMPLETA entre comillas (no resumas)
   - [v.X] indicando el versículo
   - Posición: ✅ a favor / ⚠️ matiz / ❌ en contra
4. Resumen del debate en 1-2 oraciones

REGLAS:
- Incluye TODOS los padres, no solo los principales
- Citas textuales completas entre comillas
- Cada cita con [Padre, v.X]
- Responde en español. SOLO HTML."""

            r = client.converse(
                modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
                messages=[{"role": "user", "content": [{"text": expand_prompt}]}],
                inferenceConfig={"maxTokens": 6000, "temperature": 0},
            )
            return (i, _strip_md(r['output']['message']['content'][0]['text']))

        # Phase 2: parallel (2 workers)
        all_html_parts = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(_call_chunk_phase2, i, a) for i, a in enumerate(chunk_analyses) if a]
            for f in as_completed(futures):
                try:
                    i, html = f.result()
                    all_html_parts[i] = html
                except Exception as e:
                    import sys
                    print(f"Phase2 error: {e}", file=sys.stderr, flush=True)

        # Add navigation header and stats
        father_counts = {}
        for p in patristic:
            father_counts[p['f']] = father_counts.get(p['f'], 0) + 1
        stats_html = f'<div style="padding:1rem;background:#e3f2fd;border-radius:8px;margin-bottom:1.5rem">'
        stats_html += f'<strong>📊 {len(patristic)} comentarios</strong> de {len(father_counts)} padres · '
        stats_html += f'Versículos: {min(p["v"] for p in patristic)}-{max(p["v"] for p in patristic)}<br>'
        stats_html += f'<span style="font-size:0.8rem;color:#555">Top: {", ".join(f"{k} ({v})" for k,v in sorted(father_counts.items(), key=lambda x:-x[1])[:8])}</span>'
        stats_html += '</div>'

        result = stats_html + "\n".join(p for p in all_html_parts if p)
        if not any(all_html_parts):
            result = ""
        _s3_cache_put(cache_key, result)
        return result
    except Exception:
        return ""


def _generate_grounded_exegetical(book: str, chapter: int, commentaries: dict, morphology: dict) -> str:
    """Generate exegetical synthesis: verse-by-verse, all commentators + conclusion."""
    cache_key = f"cache/{book}/{chapter}/exegetical_grounded_v2.html"
    cached = _s3_cache_get(cache_key)
    if cached:
        return cached
    import boto3
    from botocore.config import Config
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1",
                              config=Config(read_timeout=180))

        # Split verses into chunks of ~10
        verses_sorted = sorted(commentaries.keys())
        chunks = [verses_sorted[i:i+10] for i in range(0, len(verses_sorted), 10)]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _call_exeg_chunk(idx, chunk_verses):
            comm_text = ""
            for v in chunk_verses:
                comm_text += f"\n--- v.{v} ---\n"
                for c in commentaries[v]:
                    comm_text += f"[{c['name']}]: {c['text'][:700]}\n"

            prompt = f"""Genera un comentario exegético VERSO POR VERSO de {book} {chapter} (versículos {chunk_verses[0]}-{chunk_verses[-1]}) basado en estos comentaristas. SOLO HTML con estilos inline.

COMENTARIOS:
{comm_text}

Para CADA versículo genera:
<div style="margin-bottom:1.5rem;padding:1rem;border:1px solid #e0e0e0;border-radius:8px">
  <h3 style="color:#1a237e;margin-bottom:0.5rem">v.N — [palabra(s) griega(s) clave]</h3>
  <div style="line-height:1.7">[Síntesis en español integrando los comentaristas. Menciona (Robertson), (Vincent), (Expositor's), (Meyer), (Bengel), (Alford) entre paréntesis. Resalta palabras griegas. Señala acuerdos y desacuerdos.]</div>
</div>

ÉNFASIS ESPECIAL: Si algún comentarista cita uso de la palabra en literatura EXTRA-BÍBLICA (papiros, Heródoto, Tucídides, Platón, Josefo, Filón, inscripciones), INCLUYE esa referencia con detalle. Estas son las observaciones más valiosas.

REGLAS: Síntesis en español. NO copies en inglés. Resalta griego con <span style="font-family:'Noto Serif',serif;color:#1b5e20;font-weight:bold">. SOLO HTML."""

            r = client.converse(
                modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 5000, "temperature": 0},
            )
            return (idx, _strip_md(r['output']['message']['content'][0]['text']))

        all_html_parts = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(_call_exeg_chunk, i, cv) for i, cv in enumerate(chunks)]
            for f in as_completed(futures):
                try:
                    i, html = f.result()
                    all_html_parts[i] = html
                except Exception:
                    pass

        result = "\n".join(p for p in all_html_parts if p)
        _s3_cache_put(cache_key, result)
        return result
    except Exception:
        return ""


def generate_study_html(book: str, chapter: int, version: str,
                        chapter_data: dict, geo_data: dict, output_dir: Path) -> Path:
    """Generate the interactive study HTML."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Embed all data as JSON for JS interactivity
    js_data = json.dumps(chapter_data, ensure_ascii=False).replace('</','<\\/')

    verses_count = len(chapter_data["verses"])
    patristic_count = len(chapter_data["patristic"])
    xrefs_count = len(chapter_data["xrefs"])
    places_count = len(geo_data.get("places", []))

    # Father distribution for chart
    father_counts = {}
    for p in chapter_data["patristic"]:
        father_counts[p["f"]] = father_counts.get(p["f"], 0) + 1
    sorted_fathers = sorted(father_counts.items(), key=lambda x: -x[1])[:10]

    has_map = (output_dir / "map.png").exists()

    html = _build_html(book, chapter, version, js_data, verses_count, patristic_count,
                       xrefs_count, places_count, sorted_fathers, has_map, geo_data,
                       is_ot="WLC" in chapter_data.get("parallel", {}))

    html_path = output_dir / "study.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def chapter_data_is_ot(data):
    """Check if chapter has OT-style data (WLC present)."""
    return "WLC" in data.get("parallel", {})


def _build_html(book, chapter, version, js_data, verses_count, patristic_count,
                xrefs_count, places_count, sorted_fathers, has_map, geo_data, is_ot=True):
    chart_labels = json.dumps([f[0] for f in sorted_fathers])
    chart_data = json.dumps([f[1] for f in sorted_fathers])
    events_json = json.dumps(geo_data.get("events", []), ensure_ascii=False)

    map_section = ""
    if has_map:
        map_section = '''<div class="card map-container">
  <h2>🗺️ Mapa Geográfico</h2>
  <img src="map.png" alt="Mapa" id="mapImg">
  <p class="hint">Click para ampliar</p>
</div>'''

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book} {chapter} — Estudio</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root {{ --pri: #1a237e; --acc: #c62828; --bg: #f5f5f5; --card: #fff; --txt: #212121; --mut: #757575; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--txt); line-height: 1.6; }}
.container {{ max-width: 1300px; margin: 0 auto; padding: 1.5rem; }}
header {{ background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 2rem; text-align: center; border-radius: 12px; margin-bottom: 1.5rem; }}
header h1 {{ font-size: 2.2rem; }} header p {{ opacity: 0.8; }}
.stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
.stat {{ background: var(--card); padding: 1rem; border-radius: 10px; text-align: center; flex: 1; min-width: 100px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); }}
.stat .num {{ font-size: 1.8rem; font-weight: 700; color: var(--pri); }}
.stat .label {{ font-size: 0.7rem; color: var(--mut); text-transform: uppercase; }}
.grid {{ display: grid; grid-template-columns: 5fr 3fr; gap: 1.5rem; }}
@media (max-width: 1000px) {{ .grid {{ grid-template-columns: 1fr; }} }}
.card {{ background: var(--card); border-radius: 10px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }}
.card h2 {{ color: var(--pri); font-size: 1.1rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e8eaf6; }}
.verse-block {{ margin-bottom: 1rem; padding: 0.8rem; border: 1px solid #e0e0e0; border-radius: 8px; transition: border-color 0.2s; }}
.verse-block:hover {{ border-color: var(--pri); }}
.verse-line {{ margin-bottom: 0.3rem; }}
.verse-line.main {{ font-size: 1rem; }}
.verse-line.original {{ font-size: 0.95rem; color: #333; direction: rtl; font-family: 'SBL Hebrew', 'Ezra SIL', serif; }}
.verse-line.greek {{ font-size: 0.92rem; color: #1b5e20; font-family: 'Noto Serif', Georgia, serif; direction: ltr; }}
.verse-line.lxx {{ font-size: 0.88rem; color: #4a148c; font-family: 'Noto Serif', Georgia, serif; }}
.trans-toggle {{ font-size: 0.7rem; cursor: pointer; color: var(--mut); margin-left: 0.3rem; user-select: none; }}
.trans-toggle:hover {{ color: var(--pri); }}
.verse-line.main.collapsed {{ display: none; }}
.collapsed {{ display: none; }}
.vnum {{ font-weight: 700; color: var(--acc); font-size: 0.8rem; margin-right: 0.3rem; }}
.vlabel {{ font-size: 0.65rem; color: var(--mut); font-weight: 600; text-transform: uppercase; margin-right: 0.3rem; }}
.verse-footer {{ display: flex; gap: 0.5rem; align-items: center; margin-top: 0.4rem; flex-wrap: wrap; }}
.vbtn {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; border: 1px solid #ccc; background: #fafafa; cursor: pointer; transition: all 0.15s; }}
.vbtn:hover {{ background: var(--pri); color: white; border-color: var(--pri); }}
.vbtn.patr {{ background: #fce4ec; border-color: #e91e63; color: #880e4f; }}
.vbtn.variant {{ background: #fff3e0; border-color: #ff9800; color: #e65100; }}
.morph-word {{ display: inline; cursor: pointer; border-bottom: 1px dotted #999; }}
.morph-word:hover {{ background: #bbdefb; border-radius: 3px; }}
.word-tip {{ display: none; position: absolute; background: #333; color: white; padding: 8px 12px; border-radius: 6px; font-size: 0.78rem; z-index: 50; max-width: 320px; line-height: 1.4; pointer-events: none; }}
.popup {{ display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 20px 60px rgba(0,0,0,0.3); z-index: 1000; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; }}
.popup.show {{ display: block; }} .popup h3 {{ color: var(--pri); margin-bottom: 0.8rem; }}
.popup .close {{ position: absolute; top: 10px; right: 15px; font-size: 1.5rem; cursor: pointer; color: var(--mut); }}
.overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 999; }}
.overlay.show {{ display: block; }}
.patr-item {{ margin-bottom: 0.8rem; padding: 0.7rem; background: #fce4ec; border-radius: 8px; border-left: 3px solid #c62828; }}
.patr-item .father {{ font-weight: 700; color: #880e4f; font-size: 0.85rem; }}
.patr-item .work {{ color: var(--mut); font-size: 0.75rem; font-style: italic; }}
.patr-item .text {{ font-size: 0.85rem; margin-top: 0.3rem; }}
.xref {{ display: inline-block; background: #e3f2fd; padding: 3px 10px; border-radius: 14px; margin: 3px; font-size: 0.78rem; color: #1565c0; cursor: pointer; position: relative; }}
.xref:hover {{ background: #1565c0; color: white; }}
.xref-tip {{ display: none; position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 8px 12px; border-radius: 8px; font-size: 0.75rem; width: 280px; z-index: 50; line-height: 1.4; }}
.xref:hover .xref-tip {{ display: block; }}
.map-container img {{ max-width: 100%; border-radius: 8px; cursor: pointer; }}
.map-container img.zoomed {{ position: fixed; top: 2%; left: 2%; width: 96%; height: 96%; object-fit: contain; z-index: 2000; background: white; border-radius: 0; }}
.hint {{ font-size: 0.7rem; color: var(--mut); text-align: center; }}
.chart-box {{ height: 220px; }}
.timeline {{ padding-left: 1.5rem; border-left: 2px solid #c5cae9; }}
.ev-item {{ position: relative; margin-bottom: 0.8rem; padding-left: 0.8rem; }}
.ev-item::before {{ content: ''; position: absolute; left: -1.85rem; top: 0.5rem; width: 10px; height: 10px; background: var(--acc); border-radius: 50%; }}
.ev-item .place {{ font-weight: 700; color: var(--pri); }}
</style>
</head>
<body>
<div class="container">
<header><h1>{book} {chapter}</h1><p>Estudio interactivo · {version}</p></header>
<div class="stats">
  <div class="stat"><div class="num">{verses_count}</div><div class="label">Versículos</div></div>
  <div class="stat"><div class="num">{patristic_count}</div><div class="label">Patrística</div></div>
  <div class="stat"><div class="num">{xrefs_count}</div><div class="label">Refs. Cruzadas</div></div>
  <div class="stat"><div class="num">{places_count}</div><div class="label">Lugares</div></div>
</div>
{map_section}
<div class="grid">
<div class="main-col">
  <div class="card"><h2>📖 Texto</h2><div id="versesContainer"></div></div>
</div>
<div class="side-col">
  <div class="card"><h2>📊 Padres</h2><div class="chart-box"><canvas id="fathersChart"></canvas></div></div>
  <div class="card"><h2>🔗 Referencias Cruzadas</h2><div id="xrefsContainer"></div></div>
  <div class="card"><h2>📅 Eventos</h2><div class="timeline" id="eventsContainer"></div></div>
</div>
</div>
<div class="card" id="mssMapCard" style="display:none"><h2>🗺️ Manuscritos — Mapa y Línea de Tiempo</h2><div id="mssTimeline"></div><div id="mssMapContainer" style="margin-top:1rem"></div></div>
</div>
<div class="overlay" id="overlay" onclick="closePopup()"></div>
<div class="popup" id="popup"><span class="close" onclick="closePopup()">&times;</span><div id="popupContent"></div></div>
<script>
const D = {js_data};
const events = {events_json};
const isOT = {'true' if is_ot else 'false'};

// Build verses with inline original text
const vc = document.getElementById('versesContainer');
D.verses.forEach(v => {{
  const div = document.createElement('div');
  div.className = 'verse-block';
  const mainCls = isOT ? 'verse-line main' : 'verse-line main collapsed';
  const transText = (D.spanish && D.spanish[v.v]) ? D.spanish[v.v] : v.text;
  let html = `<div class="${{mainCls}}" id="trans-${{v.v}}"><span class="vnum">${{v.v}}</span><span class="vlabel">RVR</span>${{transText}}</div>`;

  // Original text line (always visible)
  if (isOT && D.parallel.WLC && D.parallel.WLC[v.v]) {{
    html += `<div class="verse-line original"><span class="vlabel">WLC</span>${{renderMorph(v.v, D.parallel.WLC[v.v])}}</div>`;
  }} else if (D.morphology[v.v] && D.morphology[v.v].length) {{
    html += `<div class="verse-line greek"><span class="vnum">${{v.v}}</span>${{renderMorph(v.v, '')}}</div>`;
  }} else if (D.parallel.MorphGNT && D.parallel.MorphGNT[v.v]) {{
    html += `<div class="verse-line greek"><span class="vnum">${{v.v}}</span>${{D.parallel.MorphGNT[v.v]}}</div>`;
  }} else if (D.parallel.SBLGNT && D.parallel.SBLGNT[v.v]) {{
    html += `<div class="verse-line greek"><span class="vnum">${{v.v}}</span>${{D.parallel.SBLGNT[v.v]}}</div>`;
  }}

  // LXX line for OT
  if (isOT && D.parallel.LXX && D.parallel.LXX[v.v]) {{
    html += `<div class="verse-line lxx"><span class="vlabel">LXX</span>${{renderLxxMorph(v.v, D.parallel.LXX[v.v])}}</div>`;
    if (D.lxx_spanish && D.lxx_spanish[v.v]) {{
      html += `<div class="verse-line" style="font-size:0.84rem;color:#6a1b9a;font-style:italic;margin-left:1rem"><span class="vlabel">LXX-ES</span>${{D.lxx_spanish[v.v]}}</div>`;
    }}
  }}

  // Toggle button for NT translation
  if (!isOT) {{
    html += `<span class="trans-toggle" onclick="toggleTrans(${{v.v}})">&#128065; ver traducción</span>`;
  }}

  // Footer buttons
  const patrCount = D.patristic.filter(p => p.v === v.v).length;
  const variants = D.apparatus.filter(a => a.v === v.v);
  html += '<div class="verse-footer">';
  if (patrCount > 0) html += `<button class="vbtn patr" onclick="showPatristic(${{v.v}})">&#10013; ${{patrCount}} comentario${{patrCount>1?'s':''}}</button>`;
  if (variants.length > 0) html += `<button class="vbtn variant" onclick="showVariants(${{v.v}})">&#9888; ${{variants.length}} variante${{variants.length>1?'s':''}}</button>`;
  const commCount = D.greek_commentaries[v.v] ? D.greek_commentaries[v.v].length : 0;
  if (commCount > 0) html += `<button class="vbtn" onclick="showExegetical(${{v.v}})" style="background:#e8f5e9;border-color:#4caf50;color:#1b5e20">&#128218; ${{commCount}} exégesis</button>`;
  html += `<button class="vbtn" onclick="showTranslations(${{v.v}})">&#128214; versiones</button>`;
  html += '</div>';

  div.innerHTML = html;
  vc.appendChild(div);
}});

function toggleTrans(v) {{
  const el = document.getElementById('trans-'+v);
  el.classList.toggle('collapsed');
}}

const TENSE_ES = {{'P':'Presente','I':'Imperfecto (pasado continuo)','F':'Futuro','A':'Aoristo (pasado puntual)','X':'Perfecto (resultado presente)','Y':'Pluscuamperfecto'}};
const VOICE_ES = {{'A':'Activa','M':'Media','P':'Pasiva','D':'Media (deponente)','O':'Pasiva (deponente)','N':'Media/Pasiva'}};
const MOOD_ES = {{'I':'Indicativo','S':'Subjuntivo','O':'Optativo','M':'Imperativo','N':'Infinitivo','P':'Participio'}};
function verbTenseEs(rmac) {{
  if (!rmac) return '';
  // CRIT-1: Hebrew OSHM codes
  if (rmac[0] === 'H' || rmac[0] === 'A') return verbTenseHeb(rmac);
  // CRIT-2: Normalize LXX dot-format (V.AAI3S → V-AAI-3S)
  let code = rmac.replace(/\./g, '-');
  if (!code.startsWith('V-')) return '';
  code = code.substring(2);
  let offset = (code[0]==='1'||code[0]==='2') ? 1 : 0;
  const t = TENSE_ES[code[offset]] || '';
  const v = VOICE_ES[code[offset+1]] || '';
  const m = MOOD_ES[code[offset+2]] || '';
  if (!t) return '';
  return `\u23f1 ${{t}}, ${{v}}, ${{m}}`;
}}

// Contextual meanings for common participial/idiomatic forms
const HEB_STEMS = {{'q':'Qal (simple activa)','N':'Nifal (pasiva/reflexiva)','p':'Piel (intensiva activa)','P':'Pual (intensiva pasiva)','t':'Hitpael (reflexiva)','H':'Hofal (causativa pasiva)','h':'Hifil (causativa activa)'}};
const HEB_CONJS = {{'p':'Perfecto (completada)','i':'Imperfecto (continua/futura)','w':'Wayyiqtol (narrativo: "y entonces…")','v':'Imperativo (orden)','r':'Participio activo','s':'Participio pasivo','a':'Infinitivo absoluto','c':'Infinitivo constructo'}};
function verbTenseHeb(code) {{
  // code like "HVqp3ms" or "HC/Vqw3ms"
  const main = code.includes('/') ? code.split('/').pop() : code.substring(1);
  if (main[0] !== 'V') return '';
  const stem = HEB_STEMS[main[1]] || main[1];
  const conj = HEB_CONJS[main[2]] || main[2];
  return `\u23f1 ${{stem}} — ${{conj}}`;
}}

const CONTEXT_MEANINGS = {{
  'λέγω_PPP': 'llamado, de nombre',
  'λέγω_PAP': 'diciendo',
  'λέγω_AAP': 'habiendo dicho',
  'ἔρχομαι_2AAP': 'habiendo venido',
  'ἔρχομαι_PNP': 'viniendo, que viene',
  'ἔρχομαι_PMP': 'viniendo',
  'ὁράω_2AAP': 'habiendo visto',
  'ἀκούω_AAP': 'habiendo oído',
  'ἀκούω_PAP': 'oyendo, al oír',
  'γίνομαι_2AMP': 'habiendo llegado a ser',
  'γίνομαι_PMP': 'llegando a ser',
  'εἰμί_PAP': 'siendo, que es',
  'πιστεύω_PAP': 'creyendo, el que cree',
  'πιστεύω_AAP': 'habiendo creído',
  'ἔχω_PAP': 'teniendo, que tiene',
  'ποιέω_PAP': 'haciendo, que hace',
  'ποιέω_AAP': 'habiendo hecho',
  'λαμβάνω_2AAP': 'habiendo recibido',
  'λαμβάνω_PAP': 'recibiendo',
  'ἀποκρίνομαι_ADP': 'respondiendo',
  'εἰσέρχομαι_2AAP': 'habiendo entrado',
  'ἐξέρχομαι_2AAP': 'habiendo salido',
  'θέλω_PAP': 'queriendo, que quiere',
  'δίδωμι_PAP': 'dando',
  'δίδωμι_AAP': 'habiendo dado',
  'γράφω_PPP': 'escrito, lo que está escrito',
  'γράφω_PAP': 'escribiendo',
  'γινώσκω_2AAP': 'habiendo conocido',
  'γινώσκω_PAP': 'conociendo',
  'ἐγείρω_APP': 'habiendo sido levantado',
  'ἐγείρω_AAP': 'habiendo levantado',
  'καλέω_PPP': 'llamado',
  'καλέω_PAP': 'llamando',
  'ἀποστέλλω_APP': 'habiendo sido enviado',
  'ἀποστέλλω_AAP': 'habiendo enviado',
  'βαπτίζω_APP': 'habiendo sido bautizado',
  'πληρόω_AAP': 'habiendo cumplido',
  'πληρόω_APP': 'habiendo sido cumplido',
  'ζάω_PAP': 'viviendo, que vive',
  'κρίνω_PAP': 'juzgando',
  'κρίνω_AAP': 'habiendo juzgado',
  'σῴζω_APP': 'habiendo sido salvado',
  'σῴζω_PAP': 'salvando',
  'ἀγαπάω_PAP': 'amando, que ama',
  'προσέρχομαι_2AAP': 'habiéndose acercado',
  'ἀναβαίνω_2AAP': 'habiendo subido',
  'καταβαίνω_2AAP': 'habiendo bajado',
  'στρέφω_2APP': 'habiéndose vuelto',
  'παραλαμβάνω_2AAP': 'habiendo tomado consigo',
  'ἐμβαίνω_2AAP': 'habiendo embarcado',
}};
function contextualMeaning(w) {{
  if (!w.m || !w.m.startsWith('V-')) return '';
  const code = w.m.substring(2);
  let offset = (code[0]==='1'||code[0]==='2') ? 1 : 0;
  const tvm = code.substring(offset, offset+3);
  // Try specific lookup
  const key1 = w.l + '_' + tvm;
  const key2 = w.l + '_' + code.substring(0, offset+3);
  if (CONTEXT_MEANINGS[key1]) return CONTEXT_MEANINGS[key1];
  if (CONTEXT_MEANINGS[key2]) return CONTEXT_MEANINGS[key2];
  // For passive participles, provide generic hint
  if (tvm[2] === 'P' && tvm[1] === 'P') return w.es ? w.es.replace('estando siendo ', '') : '';
  return '';
}}

function explainHebrewMorph(code, form, lemma) {{
  const lang = code[0] === 'H' ? 'Hebreo' : 'Arameo';
  const main = code.includes('/') ? code.split('/').pop() : code.substring(1);
  const prefixes = code.includes('/') ? code.substring(1, code.lastIndexOf('/')) : '';
  const pos = main[0];
  const posNames = {{'N':'Sustantivo','V':'Verbo','A':'Adjetivo','P':'Pronombre','R':'Preposición','C':'Conjunción','T':'Partícula','D':'Adverbio','S':'Sufijo pronominal'}};
  const genders = {{'m':'masculino','f':'femenino','b':'ambos','c':'común'}};
  const numbers = {{'s':'singular','p':'plural','d':'dual'}};
  const states = {{'a':'absoluto','c':'constructo','d':'determinado'}};
  const persons = {{'1':'1ª persona','2':'2ª persona','3':'3ª persona'}};
  let h = `<strong style="font-family:'SBL Hebrew',serif;font-size:1.2rem">${{form}}</strong>`;
  if (lemma && lemma !== form) h += ` <span style="color:#555;font-size:0.85rem">← ${{lemma}}</span>`;
  h += `<br>`;
  if (prefixes) {{
    const pfxMap = {{'b':'בְּ (en/con)','l':'לְ (a/para)','k':'כְּ (como)','m':'מִ (de/desde)','w':'וְ (y)','h':'הַ (el/la)','c':'וְ (y)','d':'הַ (artículo)','s':'שֶׁ (que/rel.)'}};
    const pfxParts = prefixes.split('/').filter(Boolean);
    if (pfxParts.length) {{
      h += `<span style="font-size:0.78rem;color:#6a1b9a">Prefijos: ${{pfxParts.map(p => pfxMap[p] || p).join(' + ')}}</span><br>`;
    }}
  }}
  if (pos === 'V') {{
    const stem = HEB_STEMS[main[1]] || main[1];
    const conj = HEB_CONJS[main[2]] || main[2];
    h += `<strong>Verbo</strong> — ${{stem}}<br>`;
    h += `${{conj}}`;
    if (main[3]) h += ` · ${{persons[main[3]] || ''}}`;
    if (main[4]) h += ` ${{genders[main[4]] || ''}}`;
    if (main[5]) h += ` ${{numbers[main[5]] || ''}}`;
  }} else if (pos === 'N' || pos === 'A') {{
    const types = {{'c':'común','p':'propio','g':'gentilicio'}};
    h += `<strong>${{posNames[pos]}}</strong>`;
    const parts = [];
    if (main[1] && types[main[1]]) parts.push(types[main[1]]);
    if (main[2] && genders[main[2]]) parts.push(genders[main[2]]);
    if (main[3] && numbers[main[3]]) parts.push(numbers[main[3]]);
    if (main[4] && states[main[4]]) parts.push(`estado ${{states[main[4]]}}`);
    if (parts.length) h += ` — ${{parts.join(', ')}}`;
  }} else if (pos === 'P') {{
    h += `<strong>Pronombre</strong>`;
    if (main[1]) h += ` · ${{persons[main[1]] || ''}}`;
    if (main[2]) h += ` ${{genders[main[2]] || ''}}`;
    if (main[3]) h += ` ${{numbers[main[3]] || ''}}`;
  }} else {{
    h += `<strong>${{posNames[pos] || pos}}</strong>`;
  }}
  // Handle suffix pronouns (after /)
  if (code.includes('/Sp') || code.includes('/S')) {{
    const sfx = code.split('/').find(p => p.startsWith('S'));
    if (sfx && sfx.length >= 4) {{
      h += `<br><span style="font-size:0.78rem;color:#c62828">Sufijo: ${{persons[sfx[2]] || ''}} ${{genders[sfx[3]] || ''}} ${{numbers[sfx[4]] || ''}}</span>`;
    }}
  }}
  return h;
}}

function explainEnding(w) {{
  const form = w.w;
  const lemma = w.l;
  let rmac = w.m || '';
  if (!rmac) return '';

  // CRIT-1: Hebrew OSHM codes
  if (rmac[0] === 'H' || rmac[0] === 'A') return explainHebrewMorph(rmac, form, lemma);
  // CRIT-2: Normalize LXX dot-format (V.AAI3S → V-AAI3S)
  rmac = rmac.replace(/\./g, '-');

  // Normalize: strip accents for comparison to find stem/ending
  const strip = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const sf = strip(form), sl = strip(lemma);
  let common = 0;
  while (common < sf.length && common < sl.length && sf[common] === sl[common]) common++;
  if (common < 2) common = Math.min(sf.length, 2);
  const stem = form.substring(0, common);
  const ending = form.substring(common);

  const stemHtml = `<strong style="font-family:'Noto Serif',serif;font-size:1.05rem">${{stem}}</strong>`;
  const endHtml = ending ? `<strong style="font-family:'Noto Serif',serif;font-size:1.05rem;color:#c62828">${{ending}}</strong>` : '';
  let header = stemHtml + endHtml + `<br>`;

  // Helper for case explanation
  const caseExplain = {{'N':'Nominativo — SUJETO (quien hace la acción)','G':'Genitivo — POSESIÓN/ORIGEN (de...)','D':'Dativo — RECEPTOR/INSTRUMENTO (a/para/con)','A':'Acusativo — OBJETO DIRECTO (recibe la acción)','V':'Vocativo — INVOCACIÓN (dirigirse a alguien)'}};
  const genders = {{'M':'masculino','F':'femenino','N':'neutro'}};
  const numbers = {{'S':'singular','P':'plural'}};

  // === INDECLINABLES ===
  if (rmac === 'CONJ') return header + `<strong>Conjunción</strong> — conecta palabras u oraciones<br><span style="font-size:0.78rem;color:#555">No cambia de forma (indeclinable)</span>`;
  if (rmac.startsWith('PREP')) return header + `<strong>Preposición</strong> — indica relación (lugar, tiempo, causa)<br><span style="font-size:0.78rem;color:#555">No cambia de forma. Rige un caso específico del sustantivo que le sigue.</span>`;
  if (rmac.startsWith('ADV')) return header + `<strong>Adverbio</strong> — modifica al verbo (cómo, cuándo, dónde)<br><span style="font-size:0.78rem;color:#555">No cambia de forma (indeclinable)</span>`;
  if (rmac.startsWith('PRT')) return header + `<strong>Partícula</strong> — palabra funcional que añade matiz<br><span style="font-size:0.78rem;color:#555">No cambia de forma. Puede indicar negación, énfasis, etc.</span>`;
  if (rmac.startsWith('INJ')) return header + `<strong>Interjección</strong> — exclamación<br><span style="font-size:0.78rem;color:#555">No cambia de forma</span>`;
  if (rmac.startsWith('HEB') || rmac.startsWith('ARAM')) return header + `<strong>Palabra hebrea/aramea</strong> transliterada al griego<br><span style="font-size:0.78rem;color:#555">No sigue declinación griega</span>`;

  // === DECLINABLES (case/gender/number) ===
  // Pronouns: P=personal, D=demonstrative, R=relative, X=indefinite, I=interrogative, S=possessive, F=reflexive, K=correlative, C=reciprocal, Q=correlative/interrogative
  const pronounTypes = {{'P':'Pronombre personal (yo, tú, él...)','D':'Pronombre demostrativo (este, ese, aquel)','R':'Pronombre relativo (que, quien, cual)','X':'Pronombre indefinido (alguien, algo, cierto)','I':'Pronombre interrogativo (¿quién? ¿qué?)','S':'Pronombre posesivo (mío, tuyo, suyo)','F':'Pronombre reflexivo (a sí mismo)','K':'Pronombre correlativo (tal, tanto)','C':'Pronombre recíproco (unos a otros)','Q':'Pronombre correlativo/interrogativo'}};
  const firstChar = rmac[0];
  if (pronounTypes[firstChar]) {{
    const c = rmac[2]; const g = rmac[3] || ''; const n = rmac[4] || '';
    let expl = header + `<strong>${{pronounTypes[firstChar]}}</strong><br>`;
    if (c && caseExplain[c]) expl += `${{caseExplain[c]}}<br>`;
    if (g || n) expl += `<span style="font-size:0.78rem;color:#555">${{genders[g]||''}} ${{numbers[n]||''}}</span>`;
    return expl;
  }}

  // Noun/Adjective/Article
  if (rmac.startsWith('N-') || rmac.startsWith('A-') || rmac.startsWith('T-')) {{
    const typeNames = {{'N':'Sustantivo','A':'Adjetivo','T':'Artículo'}};
    const c = rmac[2]; const g = rmac[3]; const n = rmac[4];
    // Handle indeclinable forms (N-PRI = proper noun indeclinable, A-NUI = numeral indeclinable)
    if (n === 'I' || (g === 'I') || rmac.includes('PRI') || rmac.includes('NUI') || rmac.includes('OI')) {{
      return header + `<strong>${{typeNames[firstChar]}}</strong> — indeclinable (no cambia de forma)<br><span style="font-size:0.78rem;color:#555">Nombre propio o préstamo de otro idioma</span>`;
    }}
    let expl = header + `<strong>${{typeNames[firstChar]}}</strong><br>`;
    expl += `${{caseExplain[c] || c}}<br>`;
    expl += `<span style="font-size:0.78rem;color:#555">${{genders[g]||g}}, ${{numbers[n]||n}}</span>`;
    return expl;
  }}

  // === VERBS ===
  if (rmac.startsWith('V-')) {{
    const code = rmac.substring(2);
    let off = (code[0]==='1'||code[0]==='2') ? 1 : 0;
    const tense = TENSE_ES[code[off]] || code[off];
    const voice = VOICE_ES[code[off+1]] || code[off+1];
    const mood = code[off+2];

    const voiceExplain = {{'A':'el sujeto HACE la acción','M':'el sujeto actúa SOBRE SÍ MISMO','P':'el sujeto RECIBE la acción','D':'el sujeto actúa sobre sí mismo (deponente)'}};
    const tenseExplain = {{'Presente':'acción en progreso (ahora)','Imperfecto (pasado continuo)':'acción continua en el pasado (estaba...)','Futuro':'acción futura (hará...)','Aoristo (pasado puntual)':'acción completada, vista como un todo (hizo)','Perfecto (resultado presente)':'acción pasada con resultado que permanece (ha hecho)','Pluscuamperfecto':'acción completada antes de otro evento pasado (había hecho)'}};

    if (mood === 'P') {{ // Participle
      const c = code[off+3]; const n = code[off+4];
      let expl = header + `<strong>Participio</strong> = adjetivo verbal ("el que...", "habiendo...")<br>`;
      expl += `<table style="font-size:0.78rem;margin:4px 0;border-collapse:collapse">`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Tiempo:</td><td style="padding:2px 6px"><strong>${{tense}}</strong> — ${{tenseExplain[tense]||''}}</td></tr>`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Voz:</td><td style="padding:2px 6px"><strong>${{voice}}</strong> — ${{voiceExplain[code[off+1]]||''}}</td></tr>`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Caso:</td><td style="padding:2px 6px">${{caseExplain[c]||c}}, ${{numbers[n]||n}}</td></tr>`;
      expl += `</table>`;
      const tDesc = (code[off]==='A'||code[off]==='2')?'habiendo':'mientras';
      expl += `<div style="margin-top:4px;padding:4px 8px;background:#e8f5e9;border-radius:4px;font-size:0.8rem">💡 "<em>${{tDesc}} [verbo]</em>" — funciona como adjetivo del ${{c==='N'?'sujeto':c==='A'?'objeto':'sustantivo'}}</div>`;
      return expl;
    }}
    if (mood === 'N') {{
      let expl = header + `<strong>Infinitivo</strong> = forma nominal del verbo<br>`;
      expl += `<span style="font-size:0.8rem">${{tense}} — ${{tenseExplain[tense]||''}}</span><br>`;
      expl += `<span style="font-size:0.8rem">${{voice}} — ${{voiceExplain[code[off+1]]||''}}</span>`;
      expl += `<div style="margin-top:4px;padding:4px 8px;background:#e8f5e9;border-radius:4px;font-size:0.8rem">💡 Equivale a "[verbo]" o "el [verbo]" en español</div>`;
      return expl;
    }}
    if (mood === 'M') {{
      const persons = {{'1':'1ª (nosotros)','2':'2ª (tú/vosotros)','3':'3ª (él/ellos)'}};
      const p = code[off+3]; const n = code[off+4];
      let expl = header + `<strong>Imperativo</strong> = ORDEN o MANDATO<br>`;
      expl += `<table style="font-size:0.78rem;margin:4px 0;border-collapse:collapse">`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Tiempo:</td><td style="padding:2px 6px"><strong>${{tense}}</strong> — ${{tenseExplain[tense]||''}}</td></tr>`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Voz:</td><td style="padding:2px 6px">${{voice}} — ${{voiceExplain[code[off+1]]||''}}</td></tr>`;
      expl += `<tr><td style="padding:2px 6px;color:#555">Persona:</td><td style="padding:2px 6px">${{persons[p]||p}} ${{numbers[n]||n}}</td></tr>`;
      expl += `</table>`;
      expl += `<div style="margin-top:4px;padding:4px 8px;background:#fff3e0;border-radius:4px;font-size:0.8rem">💡 "¡[Haz esto]!" — orden dirigida a ${{persons[p]||p}}</div>`;
      return expl;
    }}
    // Indicative/Subjunctive/Optative
    const persons = {{'1':'1ª persona (yo/nosotros)','2':'2ª persona (tú/vosotros)','3':'3ª persona (él/ellos)'}};
    const moodExplain = {{'I':'Indicativo — afirma un HECHO real','S':'Subjuntivo — POSIBILIDAD, deseo, propósito','O':'Optativo — DESEO remoto o posibilidad lejana'}};
    const p = code[off+3]; const n = code[off+4];
    let expl = header + `<strong>${{moodExplain[mood]||mood}}</strong><br>`;
    expl += `<table style="font-size:0.78rem;margin:4px 0;border-collapse:collapse">`;
    expl += `<tr><td style="padding:2px 6px;color:#555">Tiempo:</td><td style="padding:2px 6px"><strong>${{tense}}</strong> — ${{tenseExplain[tense]||''}}</td></tr>`;
    expl += `<tr><td style="padding:2px 6px;color:#555">Voz:</td><td style="padding:2px 6px"><strong>${{voice}}</strong> — ${{voiceExplain[code[off+1]]||''}}</td></tr>`;
    expl += `<tr><td style="padding:2px 6px;color:#555">Persona:</td><td style="padding:2px 6px"><strong>${{persons[p]||p}}</strong> ${{numbers[n]||n}}</td></tr>`;
    expl += `</table>`;
    return expl;
  }}

  // Fallback
  if (form !== lemma) return header + `<span style="font-size:0.8rem;color:#555">Forma flexionada de ${{lemma}}</span>`;
  return '';
}}

function renderMorph(vnum, fallbackText) {{
  const words = D.morphology[vnum];
  if (!words || !words.length) return fallbackText || '';
  return words.map((w,i) =>
    `<span class="morph-word" onmouseenter="showWordTip(event,${{vnum}},${{i}})" onmouseleave="hideWordTip()" onclick="openWordStudy(${{vnum}},${{i}})">${{w.w}}</span>`
  ).join(' ');
}}

// Word tooltip on hover
let tipEl = null;
function showWordTip(e, vnum, idx) {{
  const w = D.morphology[vnum][idx];
  if (!w) return;
  if (!tipEl) {{ tipEl = document.createElement('div'); tipEl.className = 'word-tip'; document.body.appendChild(tipEl); }}
  const ctx = contextualMeaning(w);
  const tip = ctx || (w.es && !w.es.startsWith('estando') ? w.es : w.g) || w.g || '';
  tipEl.textContent = tip;
  if (!tipEl.textContent) {{ tipEl.style.display='none'; return; }}
  tipEl.style.display = 'block';
  tipEl.style.left = e.pageX + 'px';
  tipEl.style.top = (e.pageY - 30) + 'px';
}}

function renderLxxMorph(vnum, fallbackText) {{
  if (!D.lxx_morphology) return fallbackText || '';
  const words = D.lxx_morphology[vnum];
  if (!words || !words.length) return fallbackText || '';
  return words.map((w,i) =>
    `<span class="morph-word" style="color:#4a148c" onmouseenter="showLxxTip(event,${{vnum}},${{i}})" onmouseleave="hideWordTip()" onclick="openLxxStudy(${{vnum}},${{i}})">${{w.w}}</span>`
  ).join(' ');
}}
function showLxxTip(e, vnum, idx) {{
  const w = D.lxx_morphology[vnum][idx];
  if (!w) return;
  if (!tipEl) {{ tipEl = document.createElement('div'); tipEl.className = 'word-tip'; document.body.appendChild(tipEl); }}
  const lemmaHint = (w.l && w.l !== w.w) ? ' (' + w.l + ')' : '';
  tipEl.textContent = (w.g || '') + lemmaHint;
  if (!tipEl.textContent) {{ tipEl.style.display='none'; return; }}
  tipEl.style.display = 'block';
  tipEl.style.left = e.pageX + 'px';
  tipEl.style.top = (e.pageY - 30) + 'px';
}}
function openLxxStudy(vnum, idx) {{
  const w = D.lxx_morphology[vnum][idx];
  if (!w) return;
  let html = `<div style="font-size:1.8rem;font-family:serif;margin-bottom:0.5rem">${{w.w}}</div>`;
  html += `<table style="width:100%;border-collapse:collapse;margin-bottom:1rem">`;
  html += `<tr><td style="padding:4px 8px;font-weight:700;width:120px">Lema</td><td style="padding:4px 8px;font-size:1.1rem">${{w.l}}</td></tr>`;
  if (w.s) html += `<tr><td style="padding:4px 8px;font-weight:700">Strong's</td><td style="padding:4px 8px">${{w.s}}</td></tr>`;
  if (w.m) html += `<tr><td style="padding:4px 8px;font-weight:700">Morfología</td><td style="padding:4px 8px">${{w.m}}</td></tr>`;
  if (w.g) html += `<tr><td style="padding:4px 8px;font-weight:700">Glosa</td><td style="padding:4px 8px">${{w.g}}</td></tr>`;
  html += `</table>`;
  showPopup(`LXX: ${{w.l}} (${{w.s || ''}})`, html);
}}
function hideWordTip() {{ if (tipEl) tipEl.style.display = 'none'; }}

// Open word study in new tab
function openWordStudy(vnum, idx) {{
  const w = D.morphology[vnum][idx];
  if (!w) return;
  let occ = [];
  for (const [v, words] of Object.entries(D.morphology)) {{
    words.forEach(mw => {{ if (mw.l === w.l) occ.push(parseInt(v)); }});
  }}
  const uniqueV = [...new Set(occ)].sort((a,b)=>a-b);
  const parsing = D.rmac[w.m] || w.m;

  let html = `<div style="font-size:1.8rem;font-family:serif;margin-bottom:0.5rem">${{w.w}}</div>`;
  html += `<table style="width:100%;border-collapse:collapse;margin-bottom:1rem">`;
  html += `<tr><td style="padding:4px 8px;font-weight:700;width:120px">Lema</td><td style="padding:4px 8px;font-size:1.1rem">${{w.l}}</td></tr>`;
  if (w.s) html += `<tr><td style="padding:4px 8px;font-weight:700">Strong's</td><td style="padding:4px 8px">${{w.s}}</td></tr>`;
  if (w.m) html += `<tr><td style="padding:4px 8px;font-weight:700">Análisis</td><td style="padding:4px 8px">${{parsing}}</td></tr>`;
  if (w.g) html += `<tr><td style="padding:4px 8px;font-weight:700">Glosa (EN)</td><td style="padding:4px 8px">${{w.g}}</td></tr>`;
  if (w.es) html += `<tr><td style="padding:4px 8px;font-weight:700">Glosa (ES)</td><td style="padding:4px 8px">${{w.es}}</td></tr>`;
  html += `</table>`;
  // Compound decomposition
  const comp = D.compounds[w.l];
  // Show form breakdown FIRST (most important for learning)
  if (w.m && w.w !== w.l) {{
    const endingInfo = explainEnding(w);
    html += `<div style="padding:0.7rem;background:#e8eaf6;border-radius:6px;margin-bottom:1rem;border-left:3px solid #3f51b5">`;
    html += `<strong style="color:#1a237e">📝 ${{w.w}}:</strong><br>`;
    if (endingInfo) html += `<span style="font-size:1.05rem">${{endingInfo}}</span><br>`;
    html += `<span style="color:#555;font-size:0.82rem">${{parsing}}</span>`;
    html += `</div>`;
  }}
  // Compound etymology (only if it's a compound word with prefix+root)
  if (comp && comp.parts.length > 1) {{
    html += `<div style="padding:0.7rem;background:#fff3e0;border-radius:6px;margin-bottom:1rem;border-left:3px solid #ff9800">`;
    html += `<strong style="color:#e65100">&#9881; Origen:</strong> `;
    html += comp.parts.filter(p => p.type !== 'desinencia').map(p => `<span style="font-size:1.05rem">${{p.greek}}</span> <span style="color:#555">(${{p.meaning_es}})</span>`).join(' + ');
    if (comp.meaning) html += ` <strong>→</strong> ${{comp.meaning}}`;
    if (comp.root_note) html += `<br><span style="font-size:0.82rem;color:#555;margin-top:4px;display:inline-block">${{comp.root_note}}</span>`;
    html += `</div>`;
  }}
  if (w.d) html += `<div style="padding:0.6rem;background:#e8f5e9;border-radius:6px;margin-bottom:1rem"><strong>Def:</strong> ${{w.d}}</div>`;
  html += `<div style="padding:0.5rem;background:#e3f2fd;border-radius:6px;margin-bottom:1rem"><strong>En este cap.:</strong> ${{uniqueV.length}}x (vv. ${{uniqueV.join(', ')}})</div>`;
  html += `<button onclick="openFullStudy(${{vnum}},${{idx}})" style="padding:8px 16px;background:#1a237e;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem">Abrir estudio completo en nueva tab &#8599;</button>`;
  showPopup(`${{w.l}} (${{w.s || ''}})`, html);
}}

function openFullStudy(vnum, idx) {{
  const w = D.morphology[vnum][idx];
  if (!w) return;
  let occ = [];
  for (const [v, words] of Object.entries(D.morphology)) {{
    words.forEach(mw => {{ if (mw.l === w.l) occ.push(parseInt(v)); }});
  }}
  const uniqueV = [...new Set(occ)].sort((a,b)=>a-b);
  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${{w.l}} (${{w.s}})</title>
<style>body{{font-family:Georgia,serif;max-width:800px;margin:2rem auto;padding:1rem;line-height:1.7;color:#212121}}
h1{{color:#1a237e;border-bottom:3px solid #1a237e;padding-bottom:0.5rem}}
.section{{background:#f5f5f5;padding:1rem;border-radius:8px;margin:1rem 0}}
.section h2{{color:#c62828;font-size:1.1rem;margin-bottom:0.5rem}}
a{{color:#1565c0}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px 10px;text-align:left}}th{{background:#e8eaf6}}</style></head>
<body>
<h1>${{w.w}}</h1>
<table>
<tr><th>Lema</th><td style="font-size:1.3rem">${{w.l}}</td></tr>
<tr><th>Strong's</th><td>${{w.s || 'N/A'}}</td></tr>
<tr><th>Parsing</th><td>${{w.m || 'N/A'}}</td></tr>
<tr><th>Glosa</th><td>${{w.g || 'N/A'}}</td></tr>
</table>
<div class="section"><h2>Definici\\u00f3n</h2><p>${{w.d || 'No disponible en la base de datos local.'}}</p></div>
<div class="section"><h2>Apariciones en este cap\\u00edtulo</h2>
<p><strong>${{uniqueV.length}}</strong> veces en vv. ${{uniqueV.join(', ')}}</p>
` + uniqueV.map(v => {{
    const verse = D.verses.find(vv => vv.v === v);
    return verse ? `<p><strong>v.${{v}}</strong>: ${{verse.text}}</p>` : '';
  }}).filter(Boolean).join('') + `</div>
<div class="section"><h2>Recursos externos</h2>
<ul>
${{(w.s||'').startsWith('H') ? `
<li><a href="https://www.blueletterbible.org/lexicon/${{w.s||''}}/kjv/wlc/0-1/" target="_blank">Blue Letter Bible \\u2014 Léxico hebreo</a></li>
<li><a href="https://biblehub.com/hebrew/${{(w.s||'').replace('H','')}}.htm" target="_blank">BibleHub \\u2014 Concordancia hebrea</a></li>
<li><a href="https://www.sefaria.org/search?q=${{encodeURIComponent(w.l)}}&tab=text" target="_blank">Sefaria \\u2014 Fuentes judías</a></li>
` : `
<li><a href="https://www.blueletterbible.org/lexicon/${{w.s || ''}}/kjv/tr/0-1/" target="_blank">Blue Letter Bible \\u2014 Estudio completo</a></li>
<li><a href="https://biblehub.com/greek/${{(w.s||'').replace('G','')}}.htm" target="_blank">BibleHub \\u2014 Concordancia</a></li>
<li><a href="https://www.perseus.tufts.edu/hopper/morph?l=${{encodeURIComponent(w.l)}}&la=greek" target="_blank">Perseus \\u2014 Morfolog\\u00eda</a></li>
<li><a href="https://logeion.uchicago.edu/${{encodeURIComponent(w.l)}}" target="_blank">Logeion \\u2014 LSJ + Liddell</a></li>
`}}
<li><a href="https://www.stepbible.org/?q=strong=${{w.s || ''}}" target="_blank">STEP Bible \\u2014 Todas las apariciones</a></li>
</ul></div></body></html>`;
  const blob = new Blob([html], {{type: 'text/html'}});
  window.open(URL.createObjectURL(blob), '_blank');
}}

// Cross-refs
const xc = document.getElementById('xrefsContainer');
// Group xrefs by verse
const xrefsByV = {{}};
D.xrefs.forEach(x => {{ xrefsByV[x.v] = xrefsByV[x.v] || []; xrefsByV[x.v].push(x); }});
Object.keys(xrefsByV).sort((a,b)=>a-b).forEach(v => {{
  const grp = document.createElement('div');
  grp.style.cssText = 'margin-bottom:0.6rem';
  grp.innerHTML = `<span style="font-weight:700;color:var(--acc);font-size:0.8rem">v.${{v}}</span> `;
  xrefsByV[v].forEach(x => {{
    const span = document.createElement('span');
    span.className = 'xref';
    span.style.cursor = 'pointer';
    span.textContent = x.ref;
    span.onclick = () => showXref(x);
    grp.appendChild(span);
  }});
  xc.appendChild(grp);
}});
if (!D.xrefs.length) xc.innerHTML = '<p style="color:var(--mut)">No hay referencias cruzadas.</p>';

function showXref(x) {{
  let html = `<div style="font-weight:700;color:var(--pri);margin-bottom:0.8rem;font-size:1.1rem">${{x.ref}}</div>`;
  if (x.text.gr) html += `<div style="padding:0.6rem;background:#e8f5e9;border-radius:6px;margin-bottom:0.6rem;font-family:'Noto Serif',serif;font-size:0.95rem;line-height:1.6">${{x.text.gr}}</div>`;
  if (x.text.es) html += `<div style="padding:0.6rem;background:#f5f5f5;border-radius:6px;font-size:0.9rem;line-height:1.5">${{x.text.es}}</div>`;
  if (!x.text.gr && !x.text.es) html += '<p style="color:var(--mut)">Texto no disponible.</p>';
  showPopup(`🔗 ${{x.ref}}`, html);
}}

// Events
const ec = document.getElementById('eventsContainer');
events.forEach(e => {{
  const div = document.createElement('div');
  div.className = 'ev-item';
  div.innerHTML = `<span class="place">${{e.place}}</span>: ${{e.event}}`;
  ec.appendChild(div);
}});
if (!events.length) ec.innerHTML = '<p style="color:var(--mut)">No se identificaron eventos.</p>';

// Popups
function showPopup(title, content) {{
  document.getElementById('popupContent').innerHTML = `<h3>${{title}}</h3>${{content}}`;
  document.getElementById('popup').classList.add('show');
  document.getElementById('overlay').classList.add('show');
}}
function closePopup() {{
  document.getElementById('popup').classList.remove('show');
  document.getElementById('overlay').classList.remove('show');
}}
function showPatristic(v) {{
  const refs = D.patristic.filter(p => p.v === v);
  const langBadge = (l) => l ? `<span style="display:inline-block;font-size:0.65rem;padding:1px 6px;border-radius:8px;background:${{l==='greek'?'#e8f5e9':l==='latin'?'#e3f2fd':'#f5f5f5'}};color:#555;margin-left:6px">${{l}}</span>` : '';
  let pid = 0;
  let html = refs.map(p => {{
    pid++;
    const hasOrig = p.orig && (p.lang === 'greek' || p.lang === 'latin');
    const mainText = hasOrig ? p.orig : p.t;
    const secondText = hasOrig ? p.t : (p.orig || '');
    const mainStyle = hasOrig ? 'font-family:\"Noto Serif\",serif;' : '';
    const btnLabel = hasOrig ? 'ver traducción' : (p.orig ? 'ver original' : '');
    let h = `<div class="patr-item"><span class="father">${{p.f}}</span>${{langBadge(p.lang)}}${{p.w ? ` <span class="work">(${{p.w}})</span>` : ''}}`;
    h += `<div class="text" style="${{mainStyle}}">${{mainText}}</div>`;
    if (secondText) {{
      h += `<span class="trans-toggle" onclick="document.getElementById('ptr${{pid}}').classList.toggle('collapsed')">&#128065; ${{btnLabel}}</span>`;
      h += `<div id="ptr${{pid}}" class="collapsed" style="margin-top:0.4rem;padding:0.5rem;background:#f9fbe7;border-radius:6px;font-size:0.85rem">${{secondText}}</div>`;
    }}
    // Link to original source
    const searchName = p.f.replace(/ - .*/,'').replace(/ of .*/,'');
    const workSearch = p.w ? encodeURIComponent(p.f + ' ' + p.w) : encodeURIComponent(p.f);
    h += `<div style="margin-top:0.3rem"><a href="https://www.newadvent.org/fathers/" target="_blank" style="font-size:0.7rem;color:#1565c0;text-decoration:none">📖 New Advent</a> · <a href="https://ccel.org/ccel/search?qu=${{workSearch}}" target="_blank" style="font-size:0.7rem;color:#1565c0;text-decoration:none">📚 CCEL</a> · <a href="https://www.google.com/search?q=${{workSearch}}+full+text" target="_blank" style="font-size:0.7rem;color:#1565c0;text-decoration:none">🔍 Buscar texto completo</a></div>`;
    h += `</div>`;
    return h;
  }}).join('');
  showPopup(`&#10013; v.${{v}} \u2014 Comentario Patr\u00edstico (${{refs.length}})`, html);
}}
function showTranslations(v) {{
  const labels = {{'RVR60':'Reina-Valera 1960 (ES)','RVR1909':'Reina-Valera 1909 (ES)','KJV':'King James Version','ASV':'American Standard Version','BSB':'Berean Standard Bible','Darby':'Darby Translation','LITV':"Literal Translation (Green's)",'YLT':"Young's Literal Translation",'Vulgate':'Vulgata (Latín)'}};
  let html = '';
  for (const [ver, texts] of Object.entries(D.translations)) {{
    if (texts[v]) {{
      html += `<div style="margin-bottom:0.8rem;padding:0.6rem;background:#f5f5f5;border-radius:6px;border-left:3px solid #1565c0">`;
      html += `<strong style="font-size:0.82rem;color:#1565c0">${{labels[ver]||ver}}</strong>`;
      html += `<div style="margin-top:0.3rem;font-size:0.9rem">${{texts[v]}}</div></div>`;
    }}
  }}
  if (!html) html = '<p style="color:var(--mut)">No hay versiones adicionales disponibles.</p>';
  showPopup(`&#128214; v.${{v}} \u2014 Versiones`, html);
}}
function showExegetical(v) {{
  const comms = D.greek_commentaries[v] || [];
  if (!comms.length) {{ showPopup(`&#128218; v.${{v}}`, '<p style="color:var(--mut)">No hay comentarios disponibles.</p>'); return; }}
  // Quick synthesis: first meaningful sentence from each
  let synthesis = '<div style="padding:0.7rem;background:#e8f5e9;border-radius:6px;margin-bottom:1rem;border-left:3px solid #1b5e20;line-height:1.6;font-size:0.88rem">';
  comms.forEach(c => {{
    const clean = c.text.replace(/<[^>]+>/g, '');
    const firstSentence = clean.split(/[.!?]/).filter(s => s.trim().length > 20).slice(0, 2).join('. ').trim() + '.';
    synthesis += `<strong style="color:#1b5e20">${{c.name.split("'")[0]}}:</strong> ${{firstSentence}}<br>`;
  }});
  synthesis += '</div>';
  // Collapsible full commentaries
  let eid = 0;
  let html = synthesis + comms.map(c => {{
    eid++;
    return `<div style="margin-bottom:0.5rem">` +
      `<div style="cursor:pointer;padding:0.4rem 0.7rem;background:#f5f5f5;border-radius:6px;border-left:3px solid #4caf50;display:flex;justify-content:space-between;align-items:center" onclick="document.getElementById('exg${{v}}_${{eid}}').classList.toggle('collapsed')">` +
      `<strong style="color:#1b5e20;font-size:0.8rem">${{c.name}}</strong><span style="font-size:0.65rem;color:var(--mut)">ver completo ▼</span></div>` +
      `<div id="exg${{v}}_${{eid}}" class="collapsed" style="padding:0.6rem;font-size:0.83rem;line-height:1.5;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 6px 6px">${{c.text}}</div></div>`;
  }}).join('');
  showPopup(`&#128218; v.${{v}} \u2014 Exégesis del Griego`, html);
}}
function showVariants(v) {{
  const vars = D.apparatus.filter(a => a.v === v);
  let html = '<div style="margin-bottom:1rem;padding:0.6rem;background:#e3f2fd;border-radius:6px;font-size:0.78rem">'
    + '<strong>Glosario</strong> (click en cualquier sigla)'
    + '</div>';
  html += vars.map(va => `<div style="margin-bottom:0.7rem;padding:0.6rem;background:#fff3e0;border-radius:6px">`
    + `<strong style="font-size:1rem">${{va.r}}</strong><br>`
    + `<span style="font-size:0.82rem;color:#555">${{renderMSS(va.r)}}</span><br>`
    + `<span style="font-size:0.78rem;color:var(--mut)">Tipo textual: <strong>${{va.tt}}</strong></span></div>`).join('');
  html += '<hr style="margin:1rem 0;border:none;border-top:1px solid #ddd">';
  html += '<button onclick="openTCAnalysis()" style="padding:8px 16px;background:#c62828;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem;margin-top:0.5rem">Abrir crítica textual completa &#8599;</button>';
  html += '<div style="margin-top:0.8rem;font-size:0.75rem;color:var(--mut)"><strong>Tipos textuales:</strong> '
    + '<em>Alexandrian</em> = Egipto, s.II-IV; '
    + '<em>Byzantine</em> = mayoritario, s.V+; '
    + '<em>Western</em> = Roma/N.Africa, s.II-III; '
    + '<em>Caesarean</em> = Palestina, s.III-IV</div>';
  showPopup(`&#9888; v.${{v}} — Variantes Textuales`, html);
}}

function openTCAnalysis() {{
  const tc = D.tc_analysis || '';
  if (tc.startsWith('<!') || tc.startsWith('<h') || tc.startsWith('<div')) {{
    // tc_analysis is already full HTML - open directly
    const blob = new Blob([tc], {{type:'text/html'}});
    window.open(URL.createObjectURL(blob), '_blank');
  }} else {{
    // Fallback: wrap in basic HTML
    const vars = D.apparatus;
    let varTable = vars.map(a => `<tr><td>v.${{a.v}}</td><td>${{a.r}}</td><td>${{a.ms}}</td><td>${{a.tt}}</td></tr>`).join('');
    const html = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Crítica Textual</title>
<style>body{{font-family:Georgia,serif;max-width:950px;margin:2rem auto;padding:1.5rem;line-height:1.8;color:#212121}}
h1{{color:#1a237e}}h2{{color:#c62828}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#e8eaf6}}
a{{color:#1565c0}}</style></head>
<body><h1>Crítica Textual</h1>
<table><tr><th>Vers.</th><th>Lectura</th><th>MSS</th><th>Tipo</th></tr>${{varTable}}</table>
<h2>Análisis</h2><div>${{tc}}</div>
</body></html>`;
    const blob = new Blob([html], {{type:'text/html'}});
    window.open(URL.createObjectURL(blob), '_blank');
  }}
}}

const MSS_GLOSSARY = {{
  'P66': 'Papiro 66 (Bodmer II). Fecha: c. 200 d.C. Contenido: Evangelio de Juan (casi completo). Origen: Egipto. Importancia: Uno de los testimonios m\u00e1s antiguos del NT. Texto mixto entre alejandrino y occidental. Contiene correcciones del mismo escriba.',
  'P75': 'Papiro 75 (Bodmer XIV-XV). Fecha: c. 175-225 d.C. Contenido: Lucas 3-24 y Juan 1-15. Origen: Egipto. Importancia: El papiro m\u00e1s cercano al Codex Vaticanus (B); demuestra que el texto alejandrino es muy antiguo, no una revisi\u00f3n tard\u00eda.',
  'P46': 'Papiro 46 (Chester Beatty II). Fecha: c. 200 d.C. Contenido: Ep\u00edstolas paulinas (Rom, Heb, 1-2 Cor, Ef, Gal, Fil, Col, 1 Tes). Origen: Egipto. Importancia: El testimonio m\u00e1s antiguo de Pablo. Incluye Hebreos entre Romanos y 1 Corintios.',
  'P45': 'Papiro 45 (Chester Beatty I). Fecha: c. 250 d.C. Contenido: Fragmentos de los 4 Evangelios y Hechos. Origen: Egipto. Importancia: Texto libre/parafr\u00e1stico; el escriba abrevia y reformula.',
  'P47': 'Papiro 47 (Chester Beatty III). Fecha: c. 280 d.C. Contenido: Apocalipsis 9:10-17:2. Origen: Egipto. Importancia: El papiro m\u00e1s antiguo del Apocalipsis.',
  'P72': 'Papiro 72 (Bodmer VII-VIII). Fecha: s. III-IV. Contenido: 1-2 Pedro y Judas completos. Origen: Egipto. Importancia: El testimonio m\u00e1s antiguo de estas ep\u00edstolas. Incluye textos ap\u00f3crifos en el mismo codex.',
  '\u2135': 'Codex Sinaiticus (\u2135 / Aleph / 01). Fecha: mediados s. IV (c. 330-360). Contenido: NT completo + gran parte del AT (LXX) + Ep\u00edstola de Bernab\u00e9 + Pastor de Hermas. Origen: probablemente Cesarea o Egipto. Descubierto por Tischendorf en el Monasterio de Santa Catalina (Sina\u00ed) en 1844-1859. Hoy en la British Library. Texto alejandrino de alta calidad.',
  'B': 'Codex Vaticanus (B / 03). Fecha: mediados s. IV (c. 325-350). Contenido: AT (LXX) + NT hasta Hebreos 9:14 (faltan Pastorales, Filem\u00f3n, Apocalipsis). Origen: Egipto. En la Biblioteca Vaticana desde al menos 1475. Considerado por muchos el manuscrito m\u00e1s importante del NT. Texto alejandrino puro.',
  'A': 'Codex Alexandrinus (A / 02). Fecha: s. V (c. 400-440). Contenido: AT + NT casi completos (faltan partes de Mt, Jn, 2 Cor). Incluye 1-2 Clemente. Origen: Egipto o Constantinopla. Donado al rey Carlos I de Inglaterra en 1627. Texto bizantino en Evangelios, alejandrino en el resto.',
  'C': 'Codex Ephraemi Rescriptus (C / 04). Fecha: s. V. Contenido: Fragmentos de AT y NT (palimpsesto \u2014 borrado y reescrito con sermones de Efr\u00e9n el Sirio en s. XII). Origen: Egipto. Descifrado por Tischendorf en 1840-1845. Texto mixto.',
  'C*': 'Codex Ephraemi \u2014 lectura original del escriba (primera mano), antes de cualquier correcci\u00f3n posterior. Se distingue de C\u00b2 y C\u00b3 que son correcciones de siglos posteriores.',
  'C\u00b3': 'Codex Ephraemi \u2014 tercera mano correctora (s. IX). Las correcciones tard\u00edas suelen acercar el texto al tipo bizantino dominante en esa \u00e9poca.',
  'D': 'Codex Bezae (D / 05). Fecha: s. V (c. 400). Contenido: Evangelios + Hechos (bilingue griego-lat\u00edn). Origen: sur de Francia o norte de \u00c1frica. Donado por Teodoro de Beza a Cambridge en 1581. Texto occidental con muchas lecturas \u00fanicas, especialmente en Hechos (10% m\u00e1s largo que el alejandrino).',
  'L': 'Codex Regius (L / 019). Fecha: s. VIII. Contenido: Evangelios. Origen: Egipto. Importante porque preserva un texto alejandrino en fecha tard\u00eda. Incluye el final largo y corto de Marcos.',
  'W': 'Codex Washingtonianus (W / 032). Fecha: s. IV-V. Contenido: Evangelios. Origen: Egipto. En la Smithsonian (Washington). Texto mixto que cambia de car\u00e1cter seg\u00fan la secci\u00f3n. Contiene el \"Logion de Freer\" despu\u00e9s de Mc 16:14.',
  '\u0398': 'Codex Koridethi (\u0398 / Theta / 038). Fecha: s. IX. Contenido: Evangelios. Origen: Georgia/C\u00e1ucaso. Texto cesariense en Marcos, bizantino en los dem\u00e1s evangelios.',
  '\u03a8': 'Codex Athous Lavrensis (\u03a8 / Psi / 044). Fecha: s. VIII-IX. Contenido: Evangelios (parcial), Hechos, Ep\u00edstolas. Origen: Monte Athos. Texto mixto.',
  'f1': 'Familia 1 (Familia Lake). Grupo de min\u00fasculos: 1, 118, 131, 209, 1582, etc. Identificada por Kirsopp Lake en 1902. Texto cesariense. Caracter\u00edstica notable: en Juan 7:53-8:11 (la ad\u00faltera) la colocan despu\u00e9s de Lucas 21:38.',
  'f13': 'Familia 13 (Familia Ferrar). Grupo de min\u00fasculos: 13, 69, 124, 174, 230, 346, etc. Identificada por W.H. Ferrar en 1868. Texto cesariense. Caracter\u00edstica: coloca la per\u00edcopa de la ad\u00faltera despu\u00e9s de Lucas 21:38.',
  '33': 'Min\u00fasculo 33. Fecha: s. IX. Contenido: NT excepto Apocalipsis. Llamado \"la reina de los min\u00fasculos\" por su alta calidad textual alejandrina. Uno de los pocos min\u00fasculos que rivalizan con los grandes unciales.',
  'Byz': 'Texto Bizantino (Texto Mayoritario / Koin\u00e9). Representa >80% de todos los manuscritos griegos existentes (5,000+). Dominante desde s. V en adelante. Base del Textus Receptus y la KJV. Caracter\u00edsticas: armonizaciones, adiciones explicativas, lecturas m\u00e1s suaves. La mayor\u00eda de cr\u00edticos lo consideran secundario frente al alejandrino.',
  'lat': 'Versiones latinas. Incluye: (a) Vetus Latina (\"Antigua Latina\", s. II-IV, m\u00faltiples traducciones independientes, muy valiosas por su antig\u00fcedad); (b) Vulgata de Jer\u00f3nimo (c. 382-405, revisi\u00f3n del lat\u00edn antiguo contra el griego). Las siglas espec\u00edficas son: it = Vetus Latina, vg = Vulgata.',
  'syr': 'Versiones sir\u00edacas. Incluye: (a) Diatessaron de Taciano (c. 170, armon\u00eda de los 4 evangelios); (b) Sir\u00edaca Sinaitica (sys, s. IV); (c) Sir\u00edaca Curetoniana (syc, s. V); (d) Peshitta (syp, s. V, la \"Vulgata sir\u00edaca\", can\u00f3nica para iglesias orientales). Muy importantes por su antig\u00fcedad.',
  'cop': 'Versiones coptas. Dialectos principales: (a) Sah\u00eddico (sa, Alto Egipto, s. III-IV, texto alejandrino temprano); (b) Boh\u00e1irico (bo, Bajo Egipto, s. IV-V). Importantes por confirmar lecturas alejandrinas independientemente del griego.',
  'TR': 'Textus Receptus. No es un manuscrito sino un texto impreso. Basado en unos pocos min\u00fasculos tard\u00edos disponibles a Erasmo (1516). Nombre acu\u00f1ado por los Elzevir (1633). Base de la KJV (1611) y la RVR (1569-1909). La cr\u00edtica textual moderna lo ha superado con descubrimientos de papiros y unciales m\u00e1s antiguos.',
}};
function renderMSS(mss) {{
  if (!mss) return '';
  return mss.replace(/([P\u2135\u0398\u03a8]\\d*|[A-Z][a-z\u00b3*]*|f\\d+|\\d+|Byz|lat|syr|cop|TR)/g, (m) => {{
    const info = MSS_GLOSSARY[m];
    if (info) return `<span style="cursor:pointer;border-bottom:2px dashed #1565c0;color:#1565c0;font-weight:700;padding:0 2px" onclick="event.stopPropagation();showMSS(this,'`+m+`')">${{m}}</span>`;
    return m;
  }});
}}
function showMSS(el, key) {{
  const ms = D.manuscripts[key];
  if (ms) {{
    let html = `<table style="width:100%;border-collapse:collapse;margin-bottom:1rem">`;
    html += `<tr><td style="padding:4px 8px;font-weight:700;width:130px">Nombre</td><td style="padding:4px 8px">${{ms.name}}</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Fecha</td><td style="padding:4px 8px">${{ms.date}}</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Origen</td><td style="padding:4px 8px">${{ms.origin}}</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Descubierto</td><td style="padding:4px 8px">${{ms.disc_place}} (${{ms.disc_date}})</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Contenido</td><td style="padding:4px 8px">${{ms.content}}</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Tipo textual</td><td style="padding:4px 8px">${{ms.type}}</td></tr>`;
    html += `<tr><td style="padding:4px 8px;font-weight:700">Ubicación actual</td><td style="padding:4px 8px">${{ms.location}}</td></tr>`;
    html += `</table>`;
    html += `<div style="padding:0.6rem;background:#e8f5e9;border-radius:6px;margin-bottom:0.8rem"><strong>Descripción:</strong> ${{ms.desc}}</div>`;
    html += `<div style="padding:0.6rem;background:#e3f2fd;border-radius:6px;margin-bottom:0.8rem"><strong>Confiabilidad:</strong> ${{ms.reliability}}</div>`;
    html += `<div style="padding:0.6rem;background:#f3e5f5;border-radius:6px"><strong>Validado por:</strong> ${{ms.validators}}</div>`;
    showPopup(ms.name, html);
    return;
  }}
  const info = MSS_GLOSSARY[key];
  if (!info) return;
  let tip = document.getElementById('mssTip');
  if (!tip) {{
    tip = document.createElement('div');
    tip.id = 'mssTip';
    tip.style.cssText = 'position:fixed;background:#1a237e;color:white;padding:12px 16px;border-radius:8px;font-size:0.85rem;z-index:2000;max-width:350px;box-shadow:0 4px 20px rgba(0,0,0,0.3)';
    document.body.appendChild(tip);
  }}
  tip.innerHTML = '<strong>' + key + '</strong><br>' + info;
  tip.style.display = 'block';
  const r = el.getBoundingClientRect();
  tip.style.left = r.left + 'px';
  tip.style.top = (r.bottom + 8) + 'px';
  if (tip._tid) clearTimeout(tip._tid);
  tip._tid = setTimeout(() => {{ tip.style.display = 'none'; }}, 4000);
  tip.onclick = () => {{ tip.style.display = 'none'; }};
}}

// Chart
new Chart(document.getElementById('fathersChart'), {{
  type: 'doughnut',
  data: {{ labels: {chart_labels}, datasets: [{{ data: {chart_data}, backgroundColor: ['#1a237e','#c62828','#2e7d32','#f57f17','#4a148c','#004d40','#e65100','#1565c0','#880e4f','#33691e'] }}] }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 9 }} }} }} }} }}
}});

// Map zoom
const mapImg = document.getElementById('mapImg');
if (mapImg) {{
  mapImg.addEventListener('click', () => mapImg.classList.toggle('zoomed'));
  document.addEventListener('keydown', (e) => {{ if (e.key === 'Escape' && mapImg.classList.contains('zoomed')) mapImg.classList.remove('zoomed'); }});
}}

// Manuscripts timeline and map
if (D.manuscripts && Object.keys(D.manuscripts).length && D.apparatus && D.apparatus.length) {{
  document.getElementById('mssMapCard').style.display = 'block';
  // Get relevant MSS from apparatus
  const relevantMSS = new Set();
  D.apparatus.forEach(a => {{
    (a.ms || '').replace(/([Pℵ\u0398\u03a8]\\d*|[A-Z][a-z³*]*|f\\d+|\\d+|Byz|lat|syr|cop|TR)/g, m => {{ if (D.manuscripts[m]) relevantMSS.add(m); }});
  }});
  // Build timeline
  const mssList = [...relevantMSS].map(k => ({{sigla:k, ...D.manuscripts[k]}})).sort((a,b) => a.year - b.year);
  const tlEl = document.getElementById('mssTimeline');
  if (mssList.length) {{
    const minY = mssList[0].year, maxY = mssList[mssList.length-1].year;
    const range = maxY - minY || 1;
    let tlHtml = '<div style="position:relative;height:80px;background:linear-gradient(90deg,#e8f5e9,#fff3e0,#ffebee);border-radius:8px;margin:1rem 0;padding:10px 20px">';
    tlHtml += '<div style="position:absolute;top:50%;left:20px;right:20px;height:2px;background:#666"></div>';
    mssList.forEach(ms => {{
      const pct = ((ms.year - minY) / range) * 90 + 5;
      tlHtml += `<div style="position:absolute;left:${{pct}}%;top:20%;cursor:pointer" onclick="showMSS(this,'${{ms.sigla}}')" title="${{ms.name}} (${{ms.date}})">`;
      tlHtml += `<div style="width:12px;height:12px;background:#1a237e;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`;
      tlHtml += `<div style="font-size:0.65rem;font-weight:700;text-align:center;margin-top:2px;white-space:nowrap">${{ms.sigla}}</div>`;
      tlHtml += `<div style="font-size:0.55rem;color:#666;text-align:center">${{ms.date}}</div>`;
      tlHtml += `</div>`;
    }});
    tlHtml += '</div>';
    tlEl.innerHTML = tlHtml;
  }}
  // Build simple map visualization
  const mapEl = document.getElementById('mssMapContainer');
  let mapHtml = '<div style="display:flex;flex-wrap:wrap;gap:0.5rem">';
  mssList.forEach(ms => {{
    const typeColor = ms.type === 'Alejandrino' ? '#2e7d32' : ms.type === 'Bizantino' ? '#e65100' : ms.type === 'Occidental' ? '#4a148c' : '#555';
    mapHtml += `<div style="padding:0.5rem 0.8rem;background:#f5f5f5;border-radius:8px;border-left:3px solid ${{typeColor}};cursor:pointer;font-size:0.82rem" onclick="showMSS(this,'${{ms.sigla}}')">`;
    mapHtml += `<strong>${{ms.sigla}}</strong> <span style="color:#666">${{ms.date}}</span><br>`;
    mapHtml += `<span style="font-size:0.72rem">📍 ${{ms.origin}} → ${{ms.location}}</span><br>`;
    mapHtml += `<span style="font-size:0.68rem;color:${{typeColor}};font-weight:600">${{ms.type}}</span>`;
    mapHtml += `</div>`;
  }});
  mapHtml += '</div>';
  mapHtml += '<div style="margin-top:0.8rem;font-size:0.7rem;color:var(--mut)"><span style="color:#2e7d32">■</span> Alejandrino <span style="color:#e65100">■</span> Bizantino <span style="color:#4a148c">■</span> Occidental <span style="color:#555">■</span> Mixto/Otro</div>';
  mapEl.innerHTML = mapHtml;
}}
</script>
</body>
</html>'''
