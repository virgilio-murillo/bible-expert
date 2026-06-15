"""Shared patristic & exegetical analysis generators — programmatic with collapsible cells."""
from collections import defaultdict


def _strip_md(text: str) -> str:
    """Strip markdown code fences from LLM HTML output."""
    import re
    return re.sub(r'^```\w*\n?|```$', '', text.strip()).strip()


def _generate_patristic_analysis(book: str, chapter: int, patristic: list) -> str:
    """Generate collapsible patristic analysis HTML — programmatic, no LLM."""
    if not patristic:
        return ""

    # Group by father
    by_father = defaultdict(list)
    for p in patristic:
        by_father[p['f']].append(p)
    sorted_fathers = sorted(by_father.items(), key=lambda x: -len(x[1]))

    # Group by verse
    by_verse = defaultdict(list)
    for p in patristic:
        by_verse[p['v']].append(p)

    # Stats
    stats = f'<div style="padding:1rem;background:#e3f2fd;border-radius:8px;margin-bottom:1.5rem">'
    stats += f'<strong>📊 {len(patristic)} comentarios</strong> de {len(by_father)} padres · '
    stats += f'Versículos: {min(p["v"] for p in patristic)}-{max(p["v"] for p in patristic)}<br>'
    stats += f'<span style="font-size:0.8rem;color:#555">Top: {", ".join(f"{k} ({len(v)})" for k,v in sorted_fathers[:8])}</span>'
    stats += '</div>'

    # CSS + JS for collapse
    style = '''<style>
.section{margin-bottom:1.5rem;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden}
.section-header{cursor:pointer;padding:0.8rem 1rem;background:#f5f5f5;display:flex;justify-content:space-between;align-items:center;font-weight:600;color:#1a237e}
.section-header:hover{background:#e8eaf6}
.section-body{padding:0 1rem;max-height:0;overflow:hidden;transition:max-height 0.3s ease}
.section-body.open{max-height:none;padding:0.8rem 1rem}
.patr-entry{margin-bottom:0.8rem;padding:0.6rem;border-left:3px solid #4caf50;background:#fafafa;border-radius:0 6px 6px 0}
.patr-entry .father{font-weight:700;color:#1b5e20;font-size:0.9rem}
.patr-entry .work{font-size:0.75rem;color:#666;margin-left:0.3rem}
.patr-entry .text{margin-top:0.3rem;font-size:0.88rem;line-height:1.5}
.patr-entry .orig{margin-top:0.3rem;font-family:'Noto Serif',serif;font-size:0.85rem;color:#333;display:none;padding:0.4rem;background:#f9fbe7;border-radius:4px}
.patr-entry .orig.show{display:block}
.toggle-btn{font-size:0.7rem;cursor:pointer;color:#1565c0;margin-left:0.5rem;user-select:none}
.toggle-btn:hover{text-decoration:underline}
.arrow{transition:transform 0.2s}
.arrow.open{transform:rotate(90deg)}
</style>'''

    # Build verse sections
    html = stats + style + '<div id="patrContent">'
    for v in sorted(by_verse.keys()):
        entries = by_verse[v]
        html += f'<div class="section"><div class="section-header" onclick="toggleSection(this)">'
        html += f'<span>Versículo {v} ({len(entries)} comentarios)</span><span class="arrow">▶</span></div>'
        html += '<div class="section-body">'
        for p in entries:
            html += '<div class="patr-entry">'
            html += f'<span class="father">{p["f"]}</span>'
            if p.get('w'):
                html += f'<span class="work">({p["w"]})</span>'
            if p.get('orig'):
                html += f'<span class="toggle-btn" onclick="this.parentElement.querySelector(\'.orig\').classList.toggle(\'show\')">👁 ver original</span>'
            html += f'<div class="text">{p["t"]}</div>'
            if p.get('orig'):
                html += f'<div class="orig">{p["orig"]}</div>'
            html += '</div>'
        html += '</div></div>'
    html += '</div>'

    # JS
    html += '''<script>
function toggleSection(el){
  el.querySelector('.arrow').classList.toggle('open');
  el.nextElementSibling.classList.toggle('open');
}
// Expand first section by default
document.querySelector('.section-header')?.click();
</script>'''
    return html


def _generate_grounded_exegetical(book: str, chapter: int, commentaries: dict, morphology: dict) -> str:
    """Generate collapsible exegetical analysis HTML — programmatic, no LLM."""
    if not commentaries:
        return ""

    # CSS + JS
    style = '''<style>
.verse-section{margin-bottom:1.2rem;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden}
.verse-header{cursor:pointer;padding:0.7rem 1rem;background:#e8f5e9;display:flex;justify-content:space-between;align-items:center;font-weight:600;color:#1b5e20}
.verse-header:hover{background:#c8e6c9}
.verse-body{padding:0 1rem;max-height:0;overflow:hidden;transition:max-height 0.3s ease}
.verse-body.open{max-height:none;padding:0.8rem 1rem}
.comm-entry{margin-bottom:1rem;padding:0.6rem;border-left:3px solid #1b5e20;background:#fafafa;border-radius:0 6px 6px 0}
.comm-entry .source{font-weight:700;color:#1b5e20;font-size:0.85rem}
.comm-entry .content{margin-top:0.4rem;font-size:0.88rem;line-height:1.6}
.comm-entry .content span.greek{font-family:'Noto Serif',serif;color:#1b5e20;font-weight:700}
.arrow{transition:transform 0.2s}
.arrow.open{transform:rotate(90deg)}
</style>'''

    stats = f'<div style="padding:1rem;background:#e8f5e9;border-radius:8px;margin-bottom:1.5rem">'
    stats += f'<strong>📜 Comentarios exegéticos</strong> — {len(commentaries)} versículos con análisis'
    stats += '</div>'

    html = stats + style + '<div id="exegContent">'
    for v in sorted(commentaries.keys()):
        comms = commentaries[v]
        if not comms:
            continue
        html += f'<div class="verse-section"><div class="verse-header" onclick="toggleVerse(this)">'
        html += f'<span>Versículo {v} ({len(comms)} fuentes)</span><span class="arrow">▶</span></div>'
        html += '<div class="verse-body">'
        for c in comms:
            text = c.get('text', '')
            html += '<div class="comm-entry">'
            html += f'<div class="source">{c.get("name", "Unknown")}</div>'
            html += f'<div class="content">{text}</div>'
            html += '</div>'
        html += '</div></div>'
    html += '</div>'

    html += '''<script>
function toggleVerse(el){
  el.querySelector('.arrow').classList.toggle('open');
  el.nextElementSibling.classList.toggle('open');
}
// Expand first 3 sections by default
document.querySelectorAll('.verse-header').forEach((el,i)=>{if(i<3)el.click()});
</script>'''
    return html
