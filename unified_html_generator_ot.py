"""Unified verse-by-verse analysis HTML generator.

Combines Exegetical, Patristic, and Textual Criticism analyses into a single
interactive HTML with independently expandable sections per verse.
"""
import json
import sqlite3
import re as _re
import unicodedata
from pathlib import Path
from collections import defaultdict

# Patristic metadata: church, teacher, location, link
_PATR_META = {
    # Apostolic Fathers (direct disciples)
    "Clement of Rome": {"role": "Obispo de Roma", "teacher": "Pedro y Pablo", "location": "Roma", "link": "https://es.wikipedia.org/wiki/Clemente_de_Roma"},
    "1 Clement": {"role": "Obispo de Roma", "teacher": "Pedro y Pablo", "location": "Roma", "link": "https://es.wikipedia.org/wiki/Clemente_de_Roma"},
    "Ignatius of Antioch": {"role": "Obispo de Antioquía, mártir", "teacher": "Juan", "location": "Antioquía", "link": "https://es.wikipedia.org/wiki/Ignacio_de_Antioqu%C3%ADa"},
    "Polycarp of Smyrna": {"role": "Obispo de Esmirna, mártir", "teacher": "Juan", "location": "Esmirna", "link": "https://es.wikipedia.org/wiki/Policarpo_de_Esmirna"},
    "Papias of Hierapolis": {"role": "Obispo de Hierápolis", "teacher": "Juan", "location": "Hierápolis", "link": "https://es.wikipedia.org/wiki/Pap%C3%ADas_de_Hier%C3%A1polis"},
    # Early 2nd century
    "Irenaeus": {"role": "Obispo de Lyon, mártir", "teacher": "Policarpo (discípulo de Juan)", "location": "Lyon", "link": "https://es.wikipedia.org/wiki/Ireneo_de_Lyon"},
    "Justin Martyr": {"role": "Apologista, mártir", "teacher": None, "location": "Roma", "link": "https://es.wikipedia.org/wiki/Justino_M%C3%A1rtir"},
    "Tatian the Assyrian": {"role": "Apologista", "teacher": "Justino Mártir", "location": "Siria", "link": "https://es.wikipedia.org/wiki/Taciano"},
    # North Africa
    "Tertullian": {"role": "Padre de la teología latina", "teacher": None, "location": "Cartago", "link": "https://es.wikipedia.org/wiki/Tertuliano"},
    "Cyprian": {"role": "Obispo de Cartago, mártir", "teacher": "Tertuliano (escritos)", "location": "Cartago", "link": "https://es.wikipedia.org/wiki/Cipriano_de_Cartago"},
    "Augustine of Hippo": {"role": "Obispo de Hipona, Doctor de la Iglesia", "teacher": "Ambrosio de Milán", "location": "Hipona", "link": "https://es.wikipedia.org/wiki/Agust%C3%ADn_de_Hipona"},
    "Augustine": {"role": "Obispo de Hipona, Doctor de la Iglesia", "teacher": "Ambrosio de Milán", "location": "Hipona", "link": "https://es.wikipedia.org/wiki/Agust%C3%ADn_de_Hipona"},
    # Alexandria
    "Clement of Alexandria": {"role": "Maestro catequético", "teacher": "Panteno", "location": "Alejandría", "link": "https://es.wikipedia.org/wiki/Clemente_de_Alejandr%C3%ADa"},
    "Origen": {"role": "Maestro catequético, exégeta", "teacher": "Clemente de Alejandría", "location": "Alejandría/Cesarea", "link": "https://es.wikipedia.org/wiki/Or%C3%ADgenes"},
    "Origen of Alexandria": {"role": "Maestro catequético, exégeta", "teacher": "Clemente de Alejandría", "location": "Alejandría/Cesarea", "link": "https://es.wikipedia.org/wiki/Or%C3%ADgenes"},
    "Athanasius of Alexandria": {"role": "Obispo de Alejandría, defensor de Nicea", "teacher": "Alejandro de Alejandría", "location": "Alejandría", "link": "https://es.wikipedia.org/wiki/Atanasio_de_Alejandr%C3%ADa"},
    "Cyril of Alexandria": {"role": "Patriarca de Alejandría, Concilio de Éfeso", "teacher": None, "location": "Alejandría", "link": "https://es.wikipedia.org/wiki/Cirilo_de_Alejandr%C3%ADa"},
    # Cappadocians
    "Basil of Caesarea": {"role": "Obispo de Cesarea, padre del monacato", "teacher": None, "location": "Cesarea de Capadocia", "link": "https://es.wikipedia.org/wiki/Basilio_de_Cesarea"},
    "Gregory of Nyssa": {"role": "Obispo de Nisa, teólogo místico", "teacher": "Basilio (hermano)", "location": "Nisa", "link": "https://es.wikipedia.org/wiki/Gregorio_de_Nisa"},
    "Gregory of Nazianzus": {"role": "Obispo de Constantinopla, \"el Teólogo\"", "teacher": None, "location": "Nacianzo", "link": "https://es.wikipedia.org/wiki/Gregorio_de_Nacianzo"},
    # Antioch/Constantinople
    "John Chrysostom": {"role": "Patriarca de Constantinopla, \"Boca de Oro\"", "teacher": "Diodoro de Tarso", "location": "Antioquía/Constantinopla", "link": "https://es.wikipedia.org/wiki/Juan_Cris%C3%B3stomo"},
    "Theodore of Mopsuestia": {"role": "Obispo, exégeta antioqueno", "teacher": "Diodoro de Tarso", "location": "Mopsuestia", "link": "https://es.wikipedia.org/wiki/Teodoro_de_Mopsuestia"},
    "Ephrem the Syrian": {"role": "Diácono, poeta teológico", "teacher": None, "location": "Nísibis/Edesa", "link": "https://es.wikipedia.org/wiki/Efr%C3%A9n_el_Sirio"},
    # Latin West
    "Jerome": {"role": "Traductor de la Vulgata, Doctor de la Iglesia", "teacher": "Gregorio de Nacianzo", "location": "Belén", "link": "https://es.wikipedia.org/wiki/Jer%C3%B3nimo_de_Estrid%C3%B3n"},
    "Ambrose of Milan": {"role": "Obispo de Milán, Doctor de la Iglesia", "teacher": None, "location": "Milán", "link": "https://es.wikipedia.org/wiki/Ambrosio_de_Mil%C3%A1n"},
    "Hilary of Poitiers": {"role": "Obispo, \"Atanasio de Occidente\"", "teacher": None, "location": "Poitiers", "link": "https://es.wikipedia.org/wiki/Hilario_de_Poitiers"},
    "Leo the Great": {"role": "Papa, Concilio de Calcedonia", "teacher": None, "location": "Roma", "link": "https://es.wikipedia.org/wiki/Le%C3%B3n_I_el_Magno"},
    "Gregory the Great": {"role": "Papa, reformador, Doctor de la Iglesia", "teacher": None, "location": "Roma", "link": "https://es.wikipedia.org/wiki/Gregorio_I"},
    "Gregory the Dialogist": {"role": "Papa, reformador, Doctor de la Iglesia", "teacher": None, "location": "Roma", "link": "https://es.wikipedia.org/wiki/Gregorio_I"},
    # Later exceptions
    "Maximus the Confessor": {"role": "Monje teólogo, mártir (mutilado)", "teacher": None, "location": "Constantinopla", "link": "https://es.wikipedia.org/wiki/M%C3%A1ximo_el_Confesor"},
    "John Damascene": {"role": "Monje, última síntesis patrística oriental", "teacher": None, "location": "Damasco/Mar Saba", "link": "https://es.wikipedia.org/wiki/Juan_Damasceno"},
    "Thomas Aquinas": {"role": "Teólogo escolástico, Doctor de la Iglesia", "teacher": "Alberto Magno", "location": "Italia", "link": "https://es.wikipedia.org/wiki/Tom%C3%A1s_de_Aquino"},
    # Reformers (marked as such)
    "Martin Luther": {"role": "Reformador protestante", "teacher": None, "location": "Wittenberg", "link": "https://es.wikipedia.org/wiki/Mart%C3%ADn_Lutero"},
    "John Calvin": {"role": "Reformador protestante", "teacher": None, "location": "Ginebra", "link": "https://es.wikipedia.org/wiki/Juan_Calvino"},
    "Ulrich Zwingli": {"role": "Reformador protestante", "teacher": None, "location": "Zúrich", "link": "https://es.wikipedia.org/wiki/Ulrico_Zuinglio"},
    "Erasmus of Rotterdam": {"role": "Humanista, editor del Textus Receptus", "teacher": None, "location": "Rotterdam", "link": "https://es.wikipedia.org/wiki/Erasmo_de_R%C3%B3terdam"},
    "John Wesley": {"role": "Reformador, fundador del metodismo", "teacher": None, "location": "Inglaterra", "link": "https://es.wikipedia.org/wiki/John_Wesley"},
}



def generate_unified_html(book: str, chapter: int, chapter_data: dict, output_dir: Path) -> Path:
    """Generate unified verse-by-verse analysis HTML."""
    from study_html_generator import _s3_cache_get, _s3_cache_put

    cache_key = f"cache/{book}/{chapter}/unified_analysis_v3.html"
    cached = _s3_cache_get(cache_key)
    if cached:
        p = output_dir / "unified_analysis.html"
        p.write_text(cached, encoding="utf-8")
        return p

    # Organize data by verse
    verses = chapter_data.get("verses", [])
    morphology = chapter_data.get("morphology", {})
    spanish = chapter_data.get("spanish", {})
    translations = chapter_data.get("translations", {})
    xrefs = chapter_data.get("xrefs", [])
    patristic = chapter_data.get("patristic", [])
    apparatus = chapter_data.get("apparatus", [])
    manuscripts = chapter_data.get("manuscripts", {})
    greek_commentaries = chapter_data.get("greek_commentaries", {})

    # Group by verse
    patr_by_verse = defaultdict(list)
    for p in patristic:
        patr_by_verse[p['v']].append(p)

    app_by_verse = defaultdict(list)
    for a in apparatus:
        app_by_verse[a['v']].append(a)

    xrefs_by_verse = defaultdict(list)
    for x in xrefs:
        xrefs_by_verse[x['v']].append(x)

    # Load cached LLM analyses
    tc_analyses = _load_tc_analyses(book, chapter, apparatus, verses, morphology, manuscripts)
    exeg_themes = _load_exeg_themes(book, chapter)
    patr_themes = _load_patr_themes(book, chapter)

    # If no patristic themes JSON but we have patristic data, regenerate
    if not patr_themes and patristic:
        patr_themes = _regenerate_patr_themes(book, chapter, patristic)

    # Build HTML
    verses_html = ""
    sidebar_html = ""
    for v_data in verses:
        vnum = v_data['v']
        verses_html += _render_verse_block(
            vnum, chapter_data, greek_commentaries.get(vnum, []),
            patr_by_verse.get(vnum, []), app_by_verse.get(vnum, []),
            tc_analyses.get(vnum), exeg_themes.get(vnum, []),
            patr_themes.get(vnum, []), translations, manuscripts
        )
        # Sidebar xrefs
        vxrefs = xrefs_by_verse.get(vnum, [])
        if vxrefs:
            sidebar_html += f'<div style="margin-bottom:0.8rem"><div style="font-weight:700;color:#1a237e;font-size:0.8rem">v.{vnum}</div>'
            for x in vxrefs:
                txt = x.get("text", "")
                if isinstance(txt, dict):
                    txt = txt.get("text", "")
                txt_escaped = str(txt)[:150].replace('"', '&quot;').replace("'", "\\'")
                sidebar_html += f'<div class="xref-item" title="{txt_escaped}" onclick="showXrefPopup(\'{x["ref"]}\',\'{txt_escaped}\')">&bull; {x["ref"]}</div>'
            sidebar_html += '</div>'

    js_data = json.dumps(chapter_data, ensure_ascii=False).replace('</', '<\\/')
    html = _build_unified_page(book, chapter, verses_html, sidebar_html, js_data, len(verses))

    p = output_dir / "unified_analysis.html"
    p.write_text(html, encoding="utf-8")
    _s3_cache_put(cache_key, html)
    return p


def _load_tc_analyses(book, chapter, apparatus, verses, morphology, manuscripts):
    """Load TC verdict analyses from cache or generate."""
    from study_html_generator import _s3_cache_get, _s3_cache_put, _strip_md
    cache_key = f"cache/{book}/{chapter}/tc_verdicts_v2.json"
    cached = _s3_cache_get(cache_key)
    if cached:
        try:
            return {item['verso']: item for item in json.loads(cached)}
        except (json.JSONDecodeError, KeyError):
            pass

    if not apparatus:
        return {}

    import boto3
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        variants_text = "\n".join(
            f"v.{a['v']} #{a['vid']}: {a['r']} — MSS: {a['ms']} ({a['tt']})"
            for a in apparatus
        )
        prompt = f"""Analiza estas variantes textuales de {book} {chapter}.

VARIANTES:
{variants_text}

Devuelve JSON estricto — un array con un objeto por versículo:
[{{"verso": N, "veredicto": "cuál lectura es probablemente original y por qué (2-3 oraciones)", "confianza": "alta|media|baja", "impacto": "impacto teológico (1-2 oraciones)", "criterios": [{{"nombre": "nombre del criterio", "explicacion": "por qué aplica aquí (2 oraciones)"}}]}}]

Criterios posibles: Lectio difficilior, Lectio brevior, Atestación temprana, Distribución geográfica, Anti-armonización, Paralelismo sinóptico, Error escribal, Clarificación escribal, Estructura retórica, Apoyo mayoritario, Fórmula estereotipada.
Responde en español. SOLO JSON válido."""

        r = client.converse(
            modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 4000, "temperature": 0},
        )
        raw = _strip_md(r['output']['message']['content'][0]['text'])
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        items = json.loads(raw)
        _s3_cache_put(cache_key, json.dumps(items, ensure_ascii=False))
        return {item['verso']: item for item in items}
    except Exception as e:
        print(f"[unified] TC analyses error: {e}", flush=True)
        return {}


def _load_exeg_themes(book, chapter):
    """Load exegetical themes from cache."""
    from study_html_generator import _s3_cache_get
    cache_key = f"cache/{book}/{chapter}/exegetical_themes_v2.html"
    cached = _s3_cache_get(cache_key)
    if not cached:
        return {}
    try:
        all_themes = json.loads(cached)
        by_verse = defaultdict(list)
        for t in all_themes:
            by_verse[t.get("verso", 0)].append(t)
        return dict(by_verse)
    except (json.JSONDecodeError, ValueError):
        return {}


def _load_patr_themes(book, chapter):
    """Load patristic themes from cache."""
    from study_html_generator import _s3_cache_get, _s3_cache_put
    # Try JSON cache first
    cache_key = f"cache/{book}/{chapter}/patristic_themes_v2.json"
    cached = _s3_cache_get(cache_key)
    if cached:
        try:
            all_themes = json.loads(cached)
            return _group_patr_themes_by_verse(all_themes)
        except (json.JSONDecodeError, ValueError):
            pass

    # No JSON cache — regenerate from patristic data using LLM
    # (This will happen once for chapters that were analyzed before the JSON cache was added)
    return {}


def _group_patr_themes_by_verse(all_themes):
    """Group patristic themes by verse based on citations."""
    by_verse = defaultdict(list)
    for t in all_themes:
        verses_in_theme = set()
        for cita in t.get("citas", []):
            v = cita.get("verso", 0)
            if v:
                verses_in_theme.add(v)
        for v in verses_in_theme:
            by_verse[v].append(t)
    # Deduplicate
    result = {}
    for v, themes in by_verse.items():
        seen = set()
        unique = []
        for t in themes:
            key = t.get("tema", "")
            if key not in seen:
                seen.add(key)
                unique.append(t)
        result[v] = unique
    return result


def _regenerate_patr_themes(book, chapter, patristic):
    """Regenerate patristic themes JSON from raw data using LLM."""
    from study_html_generator import _s3_cache_put, _strip_md
    import boto3
    from botocore.config import Config

    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1",
                              config=Config(read_timeout=180))

        # Build chunks of ~50 entries
        by_verse = defaultdict(list)
        for p in patristic:
            by_verse[p['v']].append(p)
        verses_sorted = sorted(by_verse.keys())

        chunks = []
        current_chunk = []
        for v in verses_sorted:
            current_chunk.extend(by_verse[v])
            if len(current_chunk) >= 50:
                chunks.append(current_chunk)
                current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _call_chunk(i, chunk):
            texts = "\n".join(f"[v.{p['v']}] {p['f']} ({p.get('w','')}): {p['t'][:500]}" for p in chunk)
            prompt = f"""Analiza estos {len(chunk)} comentarios patrísticos de {book} {chapter}.

COMENTARIOS:
{texts}

Extrae TODOS los temas teológicos. Para cada tema devuelve JSON ESTRICTO:
[{{"tema": "nombre del tema", "consenso": "alto|medio|bajo", "citas": [{{"padre": "nombre", "fecha": "siglo", "texto": "cita textual completa", "verso": N, "posicion": "favor|matiz|contra"}}], "resumen": "1-2 oraciones"}}]

REGLAS: CADA versículo en al menos un tema. Citas textuales COMPLETAS. SOLO JSON válido."""

            r = client.converse(
                modelId="global.anthropic.claude-sonnet-4-20250514-v1:0",
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 8000, "temperature": 0},
            )
            return (i, r['output']['message']['content'][0]['text'])

        chunk_results = [None] * len(chunks)
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(_call_chunk, i, chunk) for i, chunk in enumerate(chunks)]
            for f in as_completed(futures):
                try:
                    i, result = f.result()
                    chunk_results[i] = result
                except Exception as e:
                    print(f"[unified-patr] chunk error: {e}", flush=True)

        all_themes = []
        for raw in chunk_results:
            if not raw:
                continue
            try:
                clean = _strip_md(raw.strip())
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                all_themes.extend(json.loads(clean))
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[unified-patr] JSON parse error: {e}", flush=True)

        if all_themes:
            _s3_cache_put(f"cache/{book}/{chapter}/patristic_themes_v2.json",
                          json.dumps(all_themes, ensure_ascii=False))
            return _group_patr_themes_by_verse(all_themes)
    except Exception as e:
        print(f"[unified-patr] regeneration error: {e}", flush=True)
    return {}


def _render_verse_block(vnum, chapter_data, commentaries, patristic_entries,
                        apparatus_entries, tc_analysis, exeg_themes,
                        patr_themes, translations, manuscripts):
    """Render a single verse block with all expandable sections."""
    morphology = chapter_data.get("morphology", {})
    spanish = chapter_data.get("spanish", {})
    verses = {v['v']: v['text'] for v in chapter_data.get("verses", [])}
    is_ot = "WLC" in chapter_data.get("parallel", {})

    h = f'<div class="verse-block" id="vb{vnum}">'
    h += f'<div class="verse-header"><span class="vnum">{vnum}</span></div>'

    # === ALWAYS VISIBLE TEXT LINES ===
    # RVR (Spanish translation) - always visible first
    sp_text = spanish.get(vnum, verses.get(vnum, ""))
    h += f'<div class="text-line rvr-line"><span class="vlabel">RVR</span>{sp_text}</div>'

    # Hebrew/Greek original text (morphology words rendered by JS)
    if is_ot:
        h += f'<div class="text-line heb-line" id="greek-{vnum}" dir="rtl"><span class="vlabel" style="float:right;direction:ltr">WLC</span></div>'
    else:
        h += f'<div class="text-line greek-orig-line" id="greek-{vnum}"><span class="vlabel">GNT</span></div>'

    # LXX line for OT (rendered by JS)
    if is_ot:
        h += f'<div class="text-line lxx-line" id="lxx-{vnum}"><span class="vlabel">LXX</span></div>'
        # LXX-ES literal translation - always visible
        lxx_es = chapter_data.get("lxx_spanish", {})
        lxx_es_text = lxx_es.get(vnum) or lxx_es.get(str(vnum)) or ""
        if lxx_es_text:
            h += f'<div class="text-line lxx-es-line"><span class="vlabel">LXX-ES</span>{lxx_es_text}</div>'

    # === EXPANDABLE SECTIONS (badges row) ===
    badges = []
    has_exeg = bool(commentaries)
    has_patr = bool(patristic_entries) or bool(patr_themes)
    has_tc = bool(apparatus_entries)
    xrefs = [x for x in chapter_data.get("xrefs", []) if x.get("v") == vnum]

    if has_exeg:
        badges.append(f'<span class="badge badge-exeg" onclick="toggleSection(\'exeg-{vnum}\')">📜 Exégesis</span>')
    if has_patr:
        count = len(patristic_entries)
        badges.append(f'<span class="badge badge-patr" onclick="toggleSection(\'patr-{vnum}\')">✝ Patrística ({count})</span>')
    if has_tc:
        badges.append(f'<span class="badge badge-tc" onclick="toggleSection(\'tc-{vnum}\')">⚖️ Variantes</span>')

    if badges:
        h += f'<div class="badges-row">{" ".join(badges)}</div>'

    # === EXEGESIS SECTION ===
    if has_exeg:
        h += f'<div id="exeg-{vnum}" class="collapsed section-content exeg-section">'
        h += _render_exegesis_content(vnum, commentaries, exeg_themes)
        h += '</div>'

    # === PATRISTIC SECTION ===
    if has_patr:
        h += f'<div id="patr-{vnum}" class="collapsed section-content patr-section">'
        h += _render_patristic_content(vnum, patristic_entries, patr_themes)
        h += '</div>'

    # === TC SECTION ===
    if has_tc:
        h += f'<div id="tc-{vnum}" class="collapsed section-content tc-section">'
        h += _render_tc_content(vnum, apparatus_entries, tc_analysis, chapter_data, manuscripts)
        h += '</div>'

    # === XREFS SECTION — inline pills with 4-language data ===
    if xrefs:
        h += f'<div class="xref-container">'
        for x in xrefs:
            ref_text = x.get("text", {})
            if not isinstance(ref_text, dict):
                ref_text = {"es": str(ref_text)[:150]}
            es = (ref_text.get("es", "") or "").replace('"', '&quot;')
            gr = (ref_text.get("gr", "") or "").replace('"', '&quot;')
            lxx = (ref_text.get("lxx", "") or "").replace('"', '&quot;')
            en = (ref_text.get("en", "") or "").replace('"', '&quot;')
            h += (f'<span class="xref-pill" onclick="showXrefPopup(this)" '
                  f'data-ref="{x["ref"]}" data-es="{es}" data-gr="{gr}" '
                  f'data-lxx="{lxx}" data-en="{en}">{x["ref"]}</span>')
        h += '</div>'

    h += '</div>'  # close verse-block
    return h


def _render_exegesis_content(vnum, commentaries, exeg_themes):
    """Render exegesis section: commentator quotes + thematic analysis."""
    h = ''
    # Summary box with first sentences
    h += '<div class="exeg-summary">'
    for c in commentaries:
        clean = c.get("text", "").replace("<", "&lt;").replace(">", "&gt;")
        sentences = [s.strip() for s in clean.split(".") if len(s.strip()) > 20]
        first = ". ".join(sentences[:2]).strip()
        if first and not first.endswith("."):
            first += "."
        short_name = c.get("name", "").split("'")[0].strip()
        h += f'<strong style="color:#1b5e20">{short_name}:</strong> {first}<br>'
    h += '</div>'

    # Collapsible full texts
    for i, c in enumerate(commentaries):
        uid = f"uexv{vnum}_{i}"
        name = c.get("name", "")
        text = c.get("text", "").replace("<", "&lt;").replace(">", "&gt;")[:3000]
        h += '<div class="comm-item">'
        h += f'<div class="comm-header" onclick="document.getElementById(\'{uid}\').classList.toggle(\'collapsed\')">'
        h += f'<strong>{name}</strong><span class="small-arrow">ver completo ▼</span></div>'
        h += f'<div id="{uid}" class="collapsed comm-body">{text}</div>'
        h += '</div>'

    # Thematic analysis
    if exeg_themes:
        h += '<div class="themes-divider">🔍 Temas discutidos</div>'
        for theme in exeg_themes:
            h += _render_exeg_theme_inline(theme)
    return h


def _render_exeg_theme_inline(theme):
    """Render a single exegetical theme."""
    consenso = theme.get("consenso", "medio")
    color = {"alto": "#4caf50", "medio": "#ff9800", "bajo": "#f44336"}.get(consenso, "#ff9800")
    pct = {"alto": 85, "medio": 55, "bajo": 25}.get(consenso, 55)

    h = '<div class="theme-card">'
    h += f'<div class="theme-word">{theme.get("palabra", "")}</div>'
    h += f'<div class="consensus-bar"><div style="width:{pct}%;background:{color}"></div></div>'
    for op in theme.get("opiniones", []):
        pos = op.get("posicion", "favor")
        icon = {"favor": "✅", "matiz": "⚠️", "contra": "❌"}.get(pos, "•")
        border_color = {"favor": "#4caf50", "matiz": "#ff9800", "contra": "#f44336"}.get(pos, "#9e9e9e")
        h += f'<div class="opinion" style="border-left-color:{border_color}">'
        h += f'{icon} <strong>{op.get("comentarista","")}</strong> {op.get("texto","")}</div>'
    if theme.get("resumen"):
        h += f'<div class="theme-summary">{theme["resumen"]}</div>'
    h += '</div>'
    return h


def _render_patristic_content(vnum, patristic_entries, patr_themes):
    """Render patristic section: thematic analysis (themes grouped by topic with consensus)."""
    h = ''
    if patr_themes:
        for theme in patr_themes:
            h += _render_patr_theme_inline(theme, vnum)
    elif patristic_entries:
        for p in patristic_entries:
            h += '<div class="patr-citation" style="border-left-color:#9e9e9e">'
            h += f'<div class="patr-cite-header"><strong>{p.get("f","")}</strong>'
            if p.get("w"):
                h += f' <em>({p["w"]})</em>'
            h += f'</div><div class="patr-cite-text">{p.get("t","")}</div></div>'
    return h


def _render_patr_theme_inline(theme, vnum):
    """Render a patristic theme with collapsible body."""
    import hashlib
    consenso = theme.get("consenso", "medio")
    color = {"alto": "#4caf50", "medio": "#ff9800", "bajo": "#f44336"}.get(consenso, "#ff9800")
    pct = {"alto": 85, "medio": 55, "bajo": 25}.get(consenso, 55)
    uid = "pt" + hashlib.md5(f"{vnum}{theme.get('tema','')}".encode()).hexdigest()[:8]

    h = '<div class="patr-theme">'
    h += f'<div class="patr-theme-header" onclick="document.getElementById(\'{uid}\').classList.toggle(\'collapsed\');this.querySelector(\'.arrow\').classList.toggle(\'open\')">'
    h += f'<strong>{theme["tema"]}</strong>'
    h += f'<div class="consensus-bar" style="width:60px"><div style="width:{pct}%;background:{color}"></div></div>'
    h += f'<span class="consensus-label" style="color:{color}">{consenso}</span>'
    h += '<span class="arrow">▼</span>'
    h += '</div>'

    h += f'<div id="{uid}" class="collapsed" style="padding:0.5rem 0.2rem 0">'
    for cita in theme.get("citas", []):
        pos = cita.get("posicion", "favor")
        icon = {"favor": "✅", "matiz": "⚠️", "contra": "❌"}.get(pos, "•")
        border_color = {"favor": "#4caf50", "matiz": "#ff9800", "contra": "#f44336"}.get(pos, "#9e9e9e")
        fecha = f' ({cita.get("fecha","")})' if cita.get("fecha") else ''
        padre_name = cita["padre"]
        meta = _PATR_META.get(padre_name)
        h += f'<div class="patr-citation" style="border-left-color:{border_color}">'
        h += f'<div class="patr-cite-header">{icon} <strong>{padre_name}</strong>{fecha}'
        if meta:
            h += f' <span class="patr-meta">— {meta["role"]}'
            if meta.get("teacher"):
                h += f', discípulo de {meta["teacher"]}'
            if meta.get("location"):
                h += f' ({meta["location"]})'
            h += '</span>'
            if meta.get("link"):
                h += f' <a href="{meta["link"]}" target="_blank" class="patr-link">📖</a>'
        h += f' <span class="patr-verse-ref">[v.{cita.get("verso","")}]</span></div>'
        h += f'<div class="patr-cite-text">"{cita.get("texto","")}"</div>'
        h += '</div>'

    if theme.get("resumen"):
        h += f'<div class="patr-resumen">{theme["resumen"]}</div>'
    h += '</div></div>'
    return h


def _render_tc_content(vnum, apparatus_entries, tc_analysis, chapter_data, manuscripts):
    """Render textual criticism section: collation table + verdict."""
    h = ''
    morphology = chapter_data.get("morphology", {})
    verses = {v['v']: v['text'] for v in chapter_data.get("verses", [])}

    verse_text = verses.get(vnum, '')
    verse_words = verse_text.split() if verse_text else []

    # Build morph lookup for this verse + chapter-wide fallback for variant words
    morph_map = {}
    if vnum in morphology:
        for mw in morphology[vnum]:
            morph_map[mw['w']] = mw
    # Chapter-wide fallback for words not in this verse (e.g. variant readings)
    chapter_morph = {}
    for v_words in morphology.values():
        for mw in v_words:
            if mw['w'] not in chapter_morph:
                chapter_morph[mw['w']] = mw

    def _tc_word_cell(word, is_variant=False, is_context=True):
        clean_word = _re.sub(r'[^\w\u0370-\u03FF\u1F00-\u1FFF]', '', word)
        mw = morph_map.get(word) or morph_map.get(clean_word) or chapter_morph.get(word) or chapter_morph.get(clean_word)
        bg = '#f5f5f5' if is_context else ('#c8e6c9' if not is_variant else '#ffe0b2')
        tip = lemma = morph = strongs = ''
        if mw:
            tip = (mw.get('es') or mw.get('g') or '').replace('"', '&quot;')
            lemma = (mw.get('l') or '').replace('"', '&quot;')
            morph = mw.get('m', '')
            strongs = mw.get('s', '')
        return (f'<td class="tc-word-cell tc-interactive" style="background:{bg}" '
                f'data-tip="{tip}" data-lemma="{lemma}" data-morph="{morph}" data-strongs="{strongs}">{word}</td>')

    # Collation table
    for var in apparatus_entries:
        reading_words = var['r'].split()
        pos = _find_variant_pos(verse_words, reading_words)
        var_len = len(reading_words)
        if pos >= 0:
            ctx_start = max(0, pos - 2)
            ctx_end = min(len(verse_words), pos + var_len + 2)
        else:
            ctx_start = 0
            ctx_end = min(len(verse_words), 6)
            pos = 0

        pre_words = verse_words[ctx_start:pos]
        post_words = verse_words[pos + var_len:min(len(verse_words), pos + var_len + 2)]

        h += '<div style="overflow-x:auto;margin-bottom:0.5rem">'
        h += '<table class="tc-table">'
        # Header
        h += '<tr class="tc-header"><th class="tc-ms-col">MS</th>'
        for w in pre_words:
            h += f'<th class="tc-ctx">{w}</th>'
        max_cols = max(len(reading_words), max((len(a['r'].split()) for a in apparatus_entries), default=1))
        for i in range(max_cols):
            h += f'<th class="tc-var-col">⚡{i+1}</th>'
        for w in post_words:
            h += f'<th class="tc-ctx">{w}</th>'
        h += '</tr>'

        # Rows
        colors = ['#c8e6c9', '#ffe0b2', '#ffcdd2', '#e1bee7', '#b2dfdb']
        for vi, a in enumerate(apparatus_entries):
            r_words = a['r'].split()
            ms_escaped = a['ms'].replace("'", "\\'").replace('"', '&quot;')
            # Show all witnesses as individual chips (no truncation)
            sigla_list = [s.strip() for s in _re.split(r'[,;]', a['ms']) if s.strip()]
            ms_chips = ' '.join(f'<span class="ms-chip">{s}</span>' for s in sigla_list)
            h += '<tr>'
            h += f'<td class="tc-ms-cell" onclick="showMSSPanel(\'{ms_escaped}\')">{ms_chips}</td>'
            for w in pre_words:
                h += _tc_word_cell(w, is_variant=False, is_context=True)
            for i in range(max_cols):
                if i < len(r_words):
                    h += _tc_word_cell(r_words[i], is_variant=(vi > 0), is_context=False)
                else:
                    h += '<td class="tc-word-cell" style="background:#eee"></td>'
            for w in post_words:
                h += _tc_word_cell(w, is_variant=False, is_context=True)
            h += '</tr>'
        h += '</table></div>'
        break  # One table per verse (all variants shown together)

    # Verdict
    if tc_analysis:
        conf = tc_analysis.get('confianza', 'media')
        conf_color = {'alta': '#4caf50', 'media': '#ff9800', 'baja': '#f44336'}.get(conf, '#ff9800')
        conf_pct = {'alta': 90, 'media': 60, 'baja': 30}.get(conf, 60)
        h += '<div class="tc-verdict">'
        h += f'<div class="tc-verdict-text"><strong>Veredicto:</strong> {tc_analysis.get("veredicto","")}</div>'
        h += f'<div class="consensus-bar" style="max-width:200px"><div style="width:{conf_pct}%;background:{conf_color}"></div></div>'
        if tc_analysis.get('impacto'):
            h += f'<div class="tc-impact"><strong>Impacto:</strong> {tc_analysis["impacto"]}</div>'
        if tc_analysis.get('criterios'):
            h += '<div class="tc-criteria-expanded">'
            for c in tc_analysis['criterios']:
                h += f'<div class="tc-criterion-item"><strong>{c["nombre"]}</strong>'
                if c.get("explicacion"):
                    h += f'<div class="tc-criterion-exp">{c["explicacion"]}</div>'
                h += '</div>'
            h += '</div>'
        h += '</div>'
    return h


def _find_variant_pos(verse_words, reading_words):
    """Find where the variant reading occurs in the verse text."""
    def _strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()

    reading_stripped = [_strip_accents(_re.sub(r'[^\w]', '', w)) for w in reading_words if w.strip()]
    for i in range(len(verse_words)):
        vs = _strip_accents(_re.sub(r'[^\w]', '', verse_words[i]))
        if vs and reading_stripped and vs.startswith(reading_stripped[0][:3]):
            return i
    for i, vw in enumerate(verse_words):
        vs = _strip_accents(_re.sub(r'[^\w]', '', vw))
        for rs in reading_stripped:
            if rs and vs and (vs == rs or vs.startswith(rs[:4]) or rs.startswith(vs[:4])):
                return i
    return -1


def _build_unified_page(book, chapter, verses_html, sidebar_html, js_data, verse_count):
    """Build the full HTML page."""
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book} {chapter} — Análisis Unificado</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>
:root {{ --pri: #1a237e; --acc: #c62828; --bg: #f5f5f5; --card: #fff; --txt: #212121; --mut: #757575; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--txt); line-height: 1.6; }}
.layout {{ display: grid; grid-template-columns: 200px 1fr; gap: 1rem; max-width: 1400px; margin: 0 auto; padding: 1rem; }}
@media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} .sidebar {{ display: none; }} }}
header {{ grid-column: 1 / -1; background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 1.5rem 2rem; border-radius: 12px; text-align: center; }}
header h1 {{ font-size: 2rem; }} header p {{ opacity: 0.8; font-size: 0.9rem; }}
.sidebar {{ position: sticky; top: 1rem; height: calc(100vh - 2rem); overflow-y: auto; background: var(--card); border-radius: 10px; padding: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.sidebar h2 {{ font-size: 0.85rem; color: var(--pri); margin-bottom: 0.8rem; border-bottom: 2px solid #e8eaf6; padding-bottom: 0.4rem; }}
.main {{ min-width: 0; }}
.verse-block {{ background: var(--card); border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.verse-header {{ margin-bottom: 0.5rem; }}
.vnum {{ font-weight: 700; color: var(--acc); font-size: 1.1rem; }}
.greek-line {{ font-family: 'Noto Serif', Georgia, serif; font-size: 1rem; color: #1b5e20; margin-bottom: 0.4rem; line-height: 1.8; }}
.heb-line {{ font-family: 'SBL Hebrew', 'Ezra SIL', serif; color: #333; direction: rtl; unicode-bidi: bidi-override; }}
.lxx-line {{ font-family: 'Noto Serif', Georgia, serif; font-size: 0.92rem; color: #4a148c; margin-bottom: 0.3rem; line-height: 1.7; }}
.lxx-es-line {{ font-size: 0.84rem; color: #6a1b9a; font-style: italic; }}
.text-line {{ margin-bottom: 0.4rem; line-height: 1.6; padding: 0.2rem 0; }}
.rvr-line {{ font-size: 0.95rem; color: #212121; }}
.greek-orig-line {{ font-family: 'Noto Serif', Georgia, serif; color: #1b5e20; }}
.vlabel {{ display: inline-block; font-size: 0.6rem; font-weight: 700; color: #777; text-transform: uppercase; margin-right: 0.5rem; min-width: 35px; vertical-align: middle; }}
.badges-row {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0; }}
.badge {{ display: inline-block; font-size: 0.72rem; padding: 3px 10px; border-radius: 12px; cursor: pointer; transition: all 0.15s; border: 1px solid #ddd; background: #fafafa; }}
.badge:hover {{ background: #1a237e; color: white; border-color: #1a237e; }}
.badge-exeg {{ border-color: #4caf50; color: #1b5e20; background: #e8f5e9; }}
.badge-patr {{ border-color: #e91e63; color: #880e4f; background: #fce4ec; }}
.badge-tc {{ border-color: #ff9800; color: #e65100; background: #fff3e0; }}
.badge-xref {{ border-color: #2196f3; color: #0d47a1; background: #e3f2fd; }}
.xref-entry {{ padding: 0.4rem 0.6rem; margin-bottom: 0.3rem; background: #f5f5f5; border-radius: 6px; font-size: 0.85rem; border-left: 3px solid #1565c0; }}
.xref-container {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0; }}
.xref-pill {{ display: inline-block; background: #e3f2fd; padding: 3px 10px; border-radius: 14px; font-size: 0.78rem; color: #1565c0; cursor: pointer; transition: all 0.15s; }}
.xref-pill:hover {{ background: #1565c0; color: white; }}
.spanish-line {{ font-size: 0.95rem; color: #333; margin-bottom: 0.6rem; }}
.rvr-btn {{ display: inline-block; font-size: 0.78rem; padding: 3px 10px; border-radius: 14px; border: 1px solid #ccc; background: #fafafa; cursor: pointer; margin-bottom: 0.5rem; }}
.rvr-btn:hover {{ background: var(--pri); color: white; }}
.ver-line {{ font-size: 0.82rem; margin: 3px 0; }} .ver-label {{ font-weight: 600; color: var(--pri); margin-right: 0.3rem; font-size: 0.7rem; }}
.collapsed {{ display: none; }}
.section-toggle {{ cursor: pointer; padding: 0.6rem 0.8rem; margin: 0.3rem 0; border-radius: 8px; display: flex; align-items: center; gap: 0.5rem; font-weight: 600; font-size: 0.9rem; transition: background 0.15s; }}
.section-toggle:hover {{ background: #e8eaf6; }}
.section-icon {{ font-size: 1.1rem; }}
.arrow {{ font-size: 0.7rem; color: var(--mut); margin-left: auto; transition: transform 0.2s; }}
.arrow.open {{ transform: rotate(90deg); }}
.section-content {{ padding: 0.8rem; border-radius: 8px; margin-bottom: 0.5rem; }}
.exeg-section {{ background: #f1f8e9; border-left: 3px solid #1b5e20; }}
.patr-section {{ background: #fce4ec; border-left: 3px solid #c62828; }}
.tc-section {{ background: #fff3e0; border-left: 3px solid #ff9800; }}
.exeg-summary {{ padding: 0.7rem; background: #e8f5e9; border-radius: 6px; margin-bottom: 0.8rem; border-left: 3px solid #1b5e20; line-height: 1.7; font-size: 0.88rem; }}
.comm-item {{ margin-bottom: 0.4rem; }}
.comm-header {{ cursor: pointer; padding: 0.4rem 0.7rem; background: #f5f5f5; border-radius: 6px; border-left: 3px solid #4caf50; display: flex; justify-content: space-between; align-items: center; }}
.comm-header strong {{ color: #1b5e20; font-size: 0.8rem; }}
.small-arrow {{ font-size: 0.65rem; color: #888; }}
.comm-body {{ padding: 0.6rem; font-size: 0.83rem; line-height: 1.5; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 6px 6px; }}
.themes-divider {{ font-size: 0.75rem; font-weight: 600; color: #33691e; margin: 0.8rem 0 0.4rem; padding-top: 0.6rem; border-top: 1px dashed #ccc; }}
.theme-card {{ margin-bottom: 0.8rem; padding: 0.7rem; border-radius: 8px; border: 1px solid #e0e0e0; background: #f9fbe7; }}
.theme-word {{ font-weight: 700; font-size: 0.9rem; color: #33691e; margin-bottom: 0.3rem; }}
.consensus-bar {{ height: 5px; background: #e0e0e0; border-radius: 3px; margin-bottom: 0.5rem; }}
.consensus-bar > div {{ height: 100%; border-radius: 3px; }}
.consensus-label {{ font-size: 0.7rem; font-weight: 600; }}
.opinion {{ margin-bottom: 0.4rem; padding: 0.4rem 0.6rem; border-left: 3px solid #9e9e9e; background: #fff; border-radius: 0 4px 4px 0; font-size: 0.83rem; }}
.theme-summary {{ margin-top: 0.5rem; font-size: 0.82rem; color: #555; font-style: italic; }}
.patr-theme {{ margin-bottom: 1rem; border-radius: 10px; border: 1px solid #e0e0e0; background: #fff; padding: 0.8rem; }}
.patr-theme-header {{ display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.5rem; }}
.patr-citation {{ margin-bottom: 0.6rem; padding: 0.6rem 0.8rem; border-left: 3px solid #9e9e9e; background: #fafafa; border-radius: 0 6px 6px 0; }}
.patr-cite-header {{ font-weight: 700; font-size: 0.85rem; color: #333; }}
.patr-verse-ref {{ font-weight: 400; color: #777; font-size: 0.75rem; }}
.patr-cite-text {{ font-size: 0.85rem; margin-top: 0.3rem; color: #444; font-style: italic; }}
.patr-resumen {{ margin-top: 0.8rem; padding: 0.6rem; background: #e8eaf6; border-radius: 6px; font-size: 0.85rem; color: #283593; }}
.patr-entry {{ margin-bottom: 0.6rem; padding: 0.6rem; background: #fff; border-radius: 6px; border-left: 3px solid #c62828; }}
.patr-father {{ font-weight: 700; color: #880e4f; font-size: 0.85rem; }}
.patr-meta {{ font-weight: 400; color: #666; font-size: 0.78rem; }}
.patr-link {{ text-decoration: none; font-size: 0.75rem; }}
.patr-date {{ font-weight: 400; color: #999; font-size: 0.75rem; }}
.patr-work {{ color: var(--mut); font-size: 0.75rem; font-style: italic; }}
.patr-orig {{ font-family: 'Noto Serif', serif; font-size: 0.85rem; color: #333; margin: 0.3rem 0; }}
.patr-text {{ font-size: 0.85rem; color: #444; }}
.tc-table {{ border-collapse: collapse; font-size: 0.85rem; white-space: nowrap; }}
.tc-header {{ background: #1a237e; color: white; }}
.tc-header th {{ padding: 6px 10px; border: 1px solid #444; }}
.tc-ctx {{ font-weight: normal; opacity: 0.7; }}
.tc-var-col {{ font-weight: bold; }}
.tc-ms-col {{ position: sticky; left: 0; background: #1a237e; z-index: 1; }}
.tc-ms-cell {{ padding: 6px 10px; border: 1px solid #ddd; font-weight: bold; font-size: 0.75rem; position: sticky; left: 0; background: #f9f9f9; color: #1565c0; min-width: 120px; }}
.ms-chip {{ display: inline-block; padding: 1px 5px; margin: 1px; background: #e8eaf6; border-radius: 3px; font-size: 0.72rem; white-space: nowrap; }}
.tc-word-cell {{ padding: 6px 10px; border: 1px solid #ddd; font-family: 'Noto Serif', serif; }}
.tc-verdict {{ margin-top: 0.8rem; padding: 0.8rem; background: #f9f9f9; border-radius: 8px; border-left: 3px solid #1a237e; }}
.tc-verdict-text {{ font-size: 0.85rem; line-height: 1.6; margin-bottom: 0.5rem; }}
.tc-impact {{ font-size: 0.83rem; color: #555; margin-bottom: 0.5rem; }}
.tc-criteria-expanded {{ margin-top: 0.6rem; }}
.tc-criterion-item {{ padding: 6px 10px; margin: 4px 0; background: #e3f2fd; border-radius: 6px; border-left: 3px solid #1565c0; font-size: 0.82rem; }}
.tc-criterion-exp {{ color: #555; font-weight: normal; margin-top: 2px; font-size: 0.78rem; line-height: 1.4; }}
.morph-word {{ display: inline; cursor: pointer; border-bottom: 1px dotted #999; }}
.morph-word:hover {{ background: #bbdefb; border-radius: 3px; }}
.xref-item {{ font-size: 0.78rem; color: #1565c0; margin: 2px 0; cursor: pointer; padding: 2px 4px; border-radius: 4px; }}
.xref-item:hover {{ background: #e3f2fd; }}
.tc-interactive {{ cursor: pointer; position: relative; }}
.tc-interactive:hover {{ background: #bbdefb !important; }}
.tc-ms-cell {{ cursor: pointer; }}
.tc-ms-cell:hover {{ color: #0d47a1; text-decoration: underline; }}
.patr-theme-header {{ cursor: pointer; display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0; padding: 0.5rem 0; }}
.patr-theme-header:hover {{ background: #f5f5f5; border-radius: 6px; }}
.word-tip {{ display: none; position: fixed; background: #333; color: white; padding: 8px 12px; border-radius: 6px; font-size: 0.82rem; z-index: 100; max-width: 320px; pointer-events: none; line-height: 1.4; }}
.toolbar {{ grid-column: 1 / -1; display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
.tool-btn {{ padding: 4px 12px; border-radius: 14px; border: 1px solid #ccc; background: #fafafa; cursor: pointer; font-size: 0.78rem; }}
.tool-btn:hover {{ background: var(--pri); color: white; border-color: var(--pri); }}
</style>
</head>
<body>
''' + _build_unified_body(book, chapter, verses_html, sidebar_html, js_data, verse_count)

def _build_unified_body(book, chapter, verses_html, sidebar_html, js_data, verse_count):
    """Build the body HTML with JS interactivity."""
    return f'''<div class="layout">
<header>
<h1>{book} {chapter}</h1>
<p>Análisis Unificado — Exégesis · Patrística · Crítica Textual</p>
</header>
<div class="toolbar">
<button class="tool-btn" onclick="expandAll('exeg')">📜 Expandir toda Exégesis</button>
<button class="tool-btn" onclick="expandAll('patr')">👨‍🏫 Expandir toda Patrística</button>
<button class="tool-btn" onclick="expandAll('tc')">⚖️ Expandir todo TC</button>
<button class="tool-btn" onclick="collapseAll()">🔽 Colapsar todo</button>
</div>
<div class="sidebar">
<h2>🔗 Referencias Cruzadas</h2>
{sidebar_html}
</div>
<div class="main">
{verses_html}
</div>
</div>
<div class="word-tip" id="wordTip"></div>
<script>
const D = {js_data};

// Render morphology for each verse
const isOT = !!(D.parallel && D.parallel.WLC);
D.verses.forEach(v => {{
  const el = document.getElementById('greek-' + v.v);
  if (!el) return;
  const words = D.morphology[v.v];
  if (words && words.length) {{
    el.innerHTML = words.map((w, i) =>
      '<span class="morph-word" onmouseenter="showTip(event,' + v.v + ',' + i + ',false)" onmouseleave="hideTip()" onclick="openWord(' + v.v + ',' + i + ',false)">' + w.w + '</span>'
    ).join(' ');
  }} else if (D.parallel && D.parallel.MorphGNT && D.parallel.MorphGNT[v.v]) {{
    el.textContent = D.parallel.MorphGNT[v.v];
  }} else if (D.parallel && D.parallel.SBLGNT && D.parallel.SBLGNT[v.v]) {{
    el.textContent = D.parallel.SBLGNT[v.v];
  }}
  // LXX line (OT only)
  if (isOT && D.lxx_morphology && D.lxx_morphology[v.v]) {{
    const lxxEl = document.getElementById('lxx-' + v.v);
    if (lxxEl) {{
      lxxEl.innerHTML = D.lxx_morphology[v.v].map((w, i) =>
        '<span class="morph-word" style="color:#4a148c" onmouseenter="showTip(event,' + v.v + ',' + i + ',true)" onmouseleave="hideTip()" onclick="openWord(' + v.v + ',' + i + ',true)">' + w.w + '</span>'
      ).join(' ');
    }}
  }}
}});

// Tooltip
const tip = document.getElementById('wordTip');
function showTip(e, vnum, idx, isLxx) {{
  const src = isLxx ? (D.lxx_morphology||{{}}) : D.morphology;
  const w = src[vnum] && src[vnum][idx];
  if (!w) return;
  const meaning = w.es || w.g || '';
  const lemma = (w.l && w.l !== w.w) ? ' (' + w.l + ')' : '';
  if (!meaning && !lemma) return;
  tip.textContent = meaning + lemma;
  tip.style.display = 'block';
  tip.style.left = Math.min(e.clientX + 10, window.innerWidth - 340) + 'px';
  tip.style.top = (e.clientY - 35) + 'px';
}}
function hideTip() {{ tip.style.display = 'none'; }}

// Word study popup
function openWord(vnum, idx, isLxx) {{
  const src = isLxx ? (D.lxx_morphology||{{}}) : D.morphology;
  const w = src[vnum] && src[vnum][idx];
  if (!w) return;
  let h = '<div style="font-size:1.6rem;font-family:serif;margin-bottom:0.5rem">' + w.w + '</div>';
  h += '<table style="width:100%;border-collapse:collapse;margin-bottom:0.8rem">';
  h += '<tr><td style="padding:4px 8px;font-weight:700">Lema</td><td style="padding:4px 8px;font-size:1.1rem">' + w.l + '</td></tr>';
  if (w.s) h += '<tr><td style="padding:4px 8px;font-weight:700">Strong\\'s</td><td style="padding:4px 8px">' + w.s + '</td></tr>';
  if (w.m) h += '<tr><td style="padding:4px 8px;font-weight:700">Morfología</td><td style="padding:4px 8px">' + w.m + '</td></tr>';
  if (w.g) h += '<tr><td style="padding:4px 8px;font-weight:700">Glosa</td><td style="padding:4px 8px">' + w.g + '</td></tr>';
  if (w.d) h += '<tr><td style="padding:4px 8px;font-weight:700">Definición</td><td style="padding:4px 8px">' + w.d + '</td></tr>';
  h += '</table>';
  const isHeb = (w.s||'').startsWith('H');
  const num = (w.s||'').replace(/[GH]/,'');
  if (isHeb) {{
    h += '<a href="https://biblehub.com/hebrew/' + num + '.htm" target="_blank" style="color:#1565c0;margin-right:1rem">BibleHub</a>';
    h += '<a href="https://www.blueletterbible.org/lexicon/h' + num + '/kjv/wlc/0-1/" target="_blank" style="color:#1565c0;margin-right:1rem">BLB</a>';
  }} else {{
    h += '<a href="https://biblehub.com/greek/' + num + '.htm" target="_blank" style="color:#1565c0;margin-right:1rem">BibleHub</a>';
    h += '<a href="https://www.blueletterbible.org/lexicon/g' + num + '/kjv/tr/0-1/" target="_blank" style="color:#1565c0;margin-right:1rem">BLB</a>';
  }}
  h += '<a href="https://www.stepbible.org/?q=strong=' + (w.s||'') + '" target="_blank" style="color:#1565c0">STEP Bible</a>';
  showPopup(w.l + ' (' + (w.s||'') + ')', h);
}}

function showPopup(title, content) {{
  let pop = document.getElementById('wordPopup');
  if (!pop) {{
    pop = document.createElement('div');
    pop.id = 'wordPopup';
    pop.style.cssText = 'position:fixed;top:10%;right:2%;width:380px;max-height:80vh;overflow-y:auto;background:white;padding:1.5rem;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.2);z-index:1000;';
    document.body.appendChild(pop);
  }}
  pop.innerHTML = '<div style="float:right;cursor:pointer;font-size:1.3rem" onclick="this.parentElement.style.display=\\'none\\'">&times;</div><h3 style="color:#1a237e;margin:0 0 0.8rem">' + title + '</h3>' + content;
  pop.style.display = 'block';
}}

// Section toggle
function toggleSection(id) {{
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('collapsed');
  const arrow = document.getElementById('arrow-' + id);
  if (arrow) arrow.classList.toggle('open');
}}

function toggleRVR(vnum) {{
  const el = document.getElementById('rvr-' + vnum);
  if (el) el.classList.toggle('collapsed');
}}

function expandAll(type) {{
  document.querySelectorAll('[id^="' + type + '-"]').forEach(el => {{
    if (el.classList.contains('section-content')) el.classList.remove('collapsed');
  }});
  document.querySelectorAll('[id^="arrow-' + type + '-"]').forEach(el => el.classList.add('open'));
}}

function collapseAll() {{
  document.querySelectorAll('.section-content').forEach(el => el.classList.add('collapsed'));
  document.querySelectorAll('.arrow').forEach(el => el.classList.remove('open'));
}}

function showXrefPopup(el) {{
  const ref = el.dataset.ref || '';
  const es = el.dataset.es || '';
  const gr = el.dataset.gr || '';
  const lxx = el.dataset.lxx || '';
  const en = el.dataset.en || '';
  const isHeb = gr && /[\u0590-\u05FF]/.test(gr);
  let h = '<div style="font-weight:700;color:#1a237e;font-size:1.1rem;margin-bottom:0.8rem">' + ref + '</div>';
  if (es) {{
    h += '<div style="margin-bottom:0.6rem"><span style="font-size:0.65rem;font-weight:600;color:#c62828;text-transform:uppercase;display:block;margin-bottom:2px">RVR (Español)</span>';
    h += '<span style="font-size:0.9rem">' + es + '</span></div>';
  }}
  if (gr) {{
    const label = isHeb ? 'WLC (Hebreo)' : 'GNT (Griego)';
    const dir = isHeb ? 'rtl' : 'ltr';
    const font = isHeb ? "'SBL Hebrew','Ezra SIL',serif" : "'Noto Serif',Georgia,serif";
    h += '<div style="margin-bottom:0.6rem"><span style="font-size:0.65rem;font-weight:600;color:#1b5e20;text-transform:uppercase;display:block;margin-bottom:2px">' + label + '</span>';
    h += '<span style="font-size:0.9rem;font-family:' + font + ';direction:' + dir + ';display:block">' + gr + '</span></div>';
  }}
  if (lxx) {{
    h += '<div style="margin-bottom:0.6rem"><span style="font-size:0.65rem;font-weight:600;color:#4a148c;text-transform:uppercase;display:block;margin-bottom:2px">LXX (Septuaginta)</span>';
    h += '<span style="font-size:0.9rem;font-family:\'Noto Serif\',serif;color:#4a148c">' + lxx + '</span></div>';
  }}
  if (en) {{
    h += '<div style="margin-bottom:0.6rem"><span style="font-size:0.65rem;font-weight:600;color:#616161;text-transform:uppercase;display:block;margin-bottom:2px">KJV (English)</span>';
    h += '<span style="font-size:0.9rem;color:#333">' + en + '</span></div>';
  }}
  showPopup('🔗 ' + ref, h);
}}

// Keyboard navigation
let currentVerse = 1;
const observer = new IntersectionObserver(entries => {{
  entries.forEach(e => {{ if (e.isIntersecting) currentVerse = parseInt(e.target.id.replace('vb','')) || currentVerse; }});
}}, {{threshold: 0.3}});
document.querySelectorAll('.verse-block').forEach(vb => observer.observe(vb));

document.addEventListener('keydown', function(e) {{
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const VC = D.verses.length;
  if (e.key==='j') {{ currentVerse=Math.min(currentVerse+1,VC); document.getElementById('vb'+currentVerse)?.scrollIntoView({{behavior:'smooth',block:'start'}}); }}
  if (e.key==='k') {{ currentVerse=Math.max(currentVerse-1,1); document.getElementById('vb'+currentVerse)?.scrollIntoView({{behavior:'smooth',block:'start'}}); }}
  if (e.key==='r') toggleRVR(currentVerse);
  if (e.key==='e') toggleSection('exeg-'+currentVerse);
  if (e.key==='p') toggleSection('patr-'+currentVerse);
}});

// TC word tooltips
document.querySelectorAll('.tc-interactive').forEach(el => {{
  el.addEventListener('mouseenter', e => {{
    const t = el.dataset.tip || '';
    const l = el.dataset.lemma || '';
    const m = el.dataset.morph || '';
    if (!l && !t) return;
    tip.innerHTML = '<strong>' + l + '</strong>' + (m ? ' <span style="opacity:0.7">[' + m + ']</span>' : '') + (t ? '<br>' + t : '');
    tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX + 10, window.innerWidth - 340) + 'px';
    tip.style.top = (e.clientY - 40) + 'px';
  }});
  el.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});
  el.addEventListener('click', () => {{
    const s = el.dataset.strongs;
    if (s) window.open('https://www.blueletterbible.org/lexicon/' + s + '/kjv/tr/0-1/', '_blank');
  }});
}});

// MS panel - comprehensible manuscript viewer
const MSS_INFO = {{
  'א': {{name:'Codex Sinaiticus', date:'s.IV', desc:'Manuscrito completo más antiguo del NT. Descubierto en el Sinaí.'}},
  'A': {{name:'Codex Alexandrinus', date:'s.V', desc:'Manuscrito casi completo. Origen egipcio.'}},
  'B': {{name:'Codex Vaticanus', date:'s.IV', desc:'Considerado el más confiable. Biblioteca Vaticana.'}},
  'C': {{name:'Codex Ephraemi', date:'s.V', desc:'Palimpsesto. Texto borrado y reescrito con sermones.'}},
  'D': {{name:'Codex Bezae', date:'s.V', desc:'Bilingüe griego-latín. Texto occidental, muchas variantes únicas.'}},
  'L': {{name:'Codex Regius', date:'s.VIII', desc:'Importante testigo del texto alejandrino.'}},
  'W': {{name:'Codex Washingtonianus', date:'s.V', desc:'Texto mixto. Contiene el \"Logion de Freer\" en Marcos.'}},
  'Δ': {{name:'Codex Sangallensis', date:'s.IX', desc:'Bilingüe griego-latín de los Evangelios.'}},
  'Θ': {{name:'Codex Koridethi', date:'s.IX', desc:'Evangelios. Texto tipo cesareense.'}},
  'Ψ': {{name:'Codex Athous Lavrensis', date:'s.VIII-IX', desc:'Monte Athos. Texto alejandrino.'}},
  'f1': {{name:'Familia 1', date:'s.XII-XIV', desc:'Grupo de minúsculos (1, 118, 131, 209). Texto cesareense.'}},
  'f13': {{name:'Familia 13', date:'s.XI-XV', desc:'Grupo Ferrar (13, 69, 124, 346). Texto cesareense.'}},
  'Byz': {{name:'Texto Bizantino', date:'s.V+', desc:'Lectura mayoritaria. Base del Textus Receptus.'}},
  'it': {{name:'Vetus Latina', date:'s.II-IV', desc:'Traducciones latinas anteriores a la Vulgata.'}},
  'vg': {{name:'Vulgata', date:'s.IV', desc:'Traducción de Jerónimo. Estándar latino por 1000 años.'}},
  'syr': {{name:'Versiones Siríacas', date:'s.II-V', desc:'Traducciones al siríaco (Peshitta, Sinaítica, Curetoniana).'}},
  'cop': {{name:'Versiones Coptas', date:'s.III-IV', desc:'Traducciones al copto (sahídico, bohaírico). Egipto.'}},
  'arm': {{name:'Versión Armenia', date:'s.V', desc:'\"Reina de las versiones\" por su fidelidad.'}},
  'eth': {{name:'Versión Etiópica', date:'s.VI', desc:'Traducción al ge\\'ez. Canon más amplio.'}},
  'geo': {{name:'Versión Georgiana', date:'s.V', desc:'Traducción al georgiano antiguo.'}},
  'slav': {{name:'Versión Eslava', date:'s.IX', desc:'Traducción de Cirilo y Metodio.'}},
  'Lect': {{name:'Leccionarios', date:'varios', desc:'Textos litúrgicos para lectura en iglesias.'}},
}};
function showMSSPanel(mss) {{
  let panel = document.getElementById('mssPanel');
  if (!panel) {{
    panel = document.createElement('div');
    panel.id = 'mssPanel';
    panel.style.cssText = 'position:fixed;top:0;right:0;width:400px;height:100vh;background:white;box-shadow:-4px 0 20px rgba(0,0,0,0.15);z-index:1000;overflow-y:auto;padding:1.5rem;transition:transform 0.2s';
    document.body.appendChild(panel);
  }}
  const siglaList = mss.split(/[,;]/).map(s => s.trim()).filter(s => s);
  let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem"><h3 style="margin:0;color:#1a237e">📜 Testigos de esta lectura</h3><span style="cursor:pointer;font-size:1.5rem;color:#888" id="closeMSS">×</span></div>';
  html += '<p style="font-size:0.8rem;color:#666;margin-bottom:1rem">Estos manuscritos y versiones antiguas contienen esta variante textual. Click en cualquiera para más información.</p>';
  html += '<div style="display:flex;flex-direction:column;gap:6px">';
  siglaList.forEach(s => {{
    const key = Object.keys(MSS_INFO).find(k => s.startsWith(k) || s.includes(k));
    const info = key ? MSS_INFO[key] : null;
    if (info) {{
      html += '<div class="ms-sigla" data-s="' + s + '" style="padding:8px 12px;background:#f5f5f5;border-radius:6px;cursor:pointer;border-left:3px solid #1565c0">';
      html += '<div style="font-weight:bold;color:#1a237e">' + s + ' — ' + info.name + ' <span style="color:#888;font-weight:normal">(' + info.date + ')</span></div>';
      html += '<div style="font-size:0.8rem;color:#555;margin-top:2px">' + info.desc + '</div></div>';
    }} else {{
      html += '<div class="ms-sigla" data-s="' + s + '" style="padding:6px 12px;background:#fafafa;border-radius:6px;cursor:pointer;border-left:3px solid #ccc">';
      html += '<span style="font-weight:bold;color:#333">' + s + '</span></div>';
    }}
  }});
  html += '</div>';
  panel.innerHTML = html;
  document.getElementById('closeMSS').onclick = function() {{ panel.remove(); }};
  panel.querySelectorAll('.ms-sigla').forEach(el => {{
    el.onclick = function() {{ window.open('https://www.google.com/search?q=' + encodeURIComponent(el.dataset.s) + ' manuscript bible', '_blank'); }};
  }});
}}

// Xref popup
function showXrefPopup(ref, text) {{
  let panel = document.getElementById('xrefPanel');
  if (!panel) {{
    panel = document.createElement('div');
    panel.id = 'xrefPanel';
    panel.style.cssText = 'position:fixed;bottom:1rem;right:1rem;width:350px;max-height:200px;background:white;box-shadow:0 4px 20px rgba(0,0,0,0.2);z-index:1000;overflow-y:auto;padding:1rem;border-radius:10px;border:1px solid #e0e0e0';
    document.body.appendChild(panel);
  }}
  panel.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem"><strong style="color:#1a237e">' + ref + '</strong><span style="cursor:pointer;color:#888" id="closeXref">×</span></div><div style="font-size:0.85rem;line-height:1.5;color:#333">' + text + '</div>';
  document.getElementById('closeXref').onclick = function() {{ panel.remove(); }};
}}
</script>
</body>
</html>'''
