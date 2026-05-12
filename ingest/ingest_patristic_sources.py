"""Ingest patristic commentary from web sources into bible.db.

Sources:
- newadvent.org/fathers (ANF/NPNF English translations)
- ldysinger.com (bilingual Greek/Latin + English)

Targets books with <5 refs/verse: Psalms, Job, Jeremiah, Isaiah, Exodus, Leviticus, Numbers, Genesis, etc.
"""
import sqlite3, re, time, json
import concurrent.futures
from pathlib import Path
from urllib.request import urlopen, Request
from html.parser import HTMLParser

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
HEADERS = {"User-Agent": "BibleExpertBot/1.0 (academic research)"}
FETCH_DELAY = 1.0  # seconds between requests to same host


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def fetch_url(url, retries=3):
    """Fetch URL with retries and delay."""
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  FAILED: {url} — {e}", flush=True)
                return None
    return None


class TextExtractor(HTMLParser):
    """Extract text content from HTML, stripping tags."""
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'nav', 'header', 'footer'):
            self.skip = False
        if tag in ('p', 'br', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.text.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)

    def get_text(self):
        return ''.join(self.text)


def html_to_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def split_into_passages(text, father, work, min_len=80, max_len=1500):
    """Split text into passages of reasonable length."""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    passages = []
    for p in paragraphs:
        if len(p) < min_len:
            continue
        if len(p) > max_len:
            # Split on sentences
            sentences = re.split(r'(?<=[.!?])\s+', p)
            chunk = ""
            for s in sentences:
                if len(chunk) + len(s) > max_len and len(chunk) > min_len:
                    passages.append(chunk.strip())
                    chunk = s
                else:
                    chunk += " " + s
            if len(chunk.strip()) > min_len:
                passages.append(chunk.strip())
        else:
            passages.append(p)
    return passages


# ============================================================
# NEW ADVENT SOURCES (English translations from ANF/NPNF)
# ============================================================

NEWADVENT_SOURCES = [
    # Origen - Homilies on Exodus (covers Ex 25-40 tabernacle)
    {"father": "Origen", "work": "Homiliae in Exodum IX", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0205.htm",
     "covers": "Exodus"},
    # Origen - Homilies on Leviticus
    {"father": "Origen", "work": "Homiliae in Leviticum I", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0206.htm",
     "covers": "Leviticus"},
    # Origen - Homilies on Numbers
    {"father": "Origen", "work": "Homiliae in Numeros", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0207.htm",
     "covers": "Numbers"},
    # Origen - Homilies on Joshua
    {"father": "Origen", "work": "Homiliae in Josuam", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0208.htm",
     "covers": "Joshua"},
    # Origen - Homilies on Judges
    {"father": "Origen", "work": "Homiliae in Judices", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0209.htm",
     "covers": "Judges"},
    # Origen - Homilies on Jeremiah
    {"father": "Origen", "work": "Homiliae in Jeremiam", "date": "c. 240",
     "source": "ANF", "url": "https://www.newadvent.org/fathers/0214.htm",
     "covers": "Jeremiah"},
    # Chrysostom - Homilies on Genesis (67 homilies!)
    {"father": "John Chrysostom", "work": "Homiliae in Genesim", "date": "c. 388",
     "source": "NPNF1", "urls_pattern": "https://www.newadvent.org/fathers/2001{:02d}.htm",
     "urls_range": (1, 68), "covers": "Genesis"},
    # Chrysostom - Homilies on Hebrews (covers tabernacle via Heb 9)
    {"father": "John Chrysostom", "work": "In Epistolam ad Hebraeos Homilia XV", "date": "c. 403",
     "source": "NPNF1", "url": "https://www.newadvent.org/fathers/240215.htm",
     "covers": "Exodus"},
    # Augustine - Enarrationes in Psalmos (massive - 150 psalms)
    {"father": "Augustine", "work": "Enarrationes in Psalmos", "date": "c. 392-418",
     "source": "NPNF1", "urls_pattern": "https://www.newadvent.org/fathers/1801{:03d}.htm",
     "urls_range": (1, 151), "covers": "Psalms"},
    # Gregory the Great - Moralia in Job
    {"father": "Gregory the Great", "work": "Moralia in Job", "date": "c. 578-595",
     "source": "NPNF2", "urls_pattern": "https://www.newadvent.org/fathers/3601{:02d}.htm",
     "urls_range": (1, 36), "covers": "Job"},
    # Jerome - Commentary on Isaiah
    {"father": "Jerome", "work": "Commentarii in Isaiam", "date": "c. 408-410",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3015.htm",
     "covers": "Isaiah"},
    # Jerome - Commentary on Jeremiah
    {"father": "Jerome", "work": "Commentarii in Jeremiam", "date": "c. 414-416",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3007.htm",
     "covers": "Jeremiah"},
    # Jerome - Commentary on Ezekiel
    {"father": "Jerome", "work": "Commentarii in Ezechielem", "date": "c. 410-414",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3005.htm",
     "covers": "Ezekiel"},
    # Jerome - Commentary on Daniel
    {"father": "Jerome", "work": "Commentarii in Danielem", "date": "c. 407",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3004.htm",
     "covers": "Daniel"},
    # Jerome - Commentary on Minor Prophets
    {"father": "Jerome", "work": "Commentarii in Prophetas Minores", "date": "c. 406",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3006.htm",
     "covers": "Hosea,Joel,Amos,Jonah,Micah,Nahum,Habakkuk,Zephaniah,Haggai,Zechariah,Malachi"},
    # Chrysostom - Homilies on Psalms (incomplete but valuable)
    {"father": "John Chrysostom", "work": "Expositiones in Psalmos", "date": "c. 395",
     "source": "NPNF1", "url": "https://www.newadvent.org/fathers/1905.htm",
     "covers": "Psalms"},
    # Ambrose - Hexaemeron (on Genesis 1)
    {"father": "Ambrose", "work": "Hexaemeron", "date": "c. 387",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3201.htm",
     "covers": "Genesis"},
    # Basil - Hexaemeron
    {"father": "Basil of Caesarea", "work": "Hexaemeron", "date": "c. 370",
     "source": "NPNF2", "url": "https://www.newadvent.org/fathers/3201.htm",
     "covers": "Genesis"},
]

# ldysinger.com sources (bilingual)
LDYSINGER_SOURCES = [
    {"father": "Clement of Alexandria", "work": "Stromata V.6 (De Tabernaculo)",
     "date": "c. 200", "source": "PG 8",
     "url": "http://ldysinger.com/@texts/0216_clement/04_myst_interp_tabern.htm",
     "lang": "greek", "covers": "Exodus"},
    {"father": "Origen", "work": "Homiliae in Exodum (Latin/Rufinus)",
     "date": "c. 240", "source": "PG 12",
     "url": "http://ldysinger.com/@texts/0250_origen/09_introd_latin_homilies.htm",
     "lang": "latin", "covers": "Exodus"},
]


def ingest_newadvent_source(source):
    """Fetch and ingest a single New Advent source."""
    father = source["father"]
    work = source["work"]
    date = source["date"]
    src = source["source"]
    
    urls = []
    if "url" in source:
        urls = [source["url"]]
    elif "urls_pattern" in source:
        start, end = source["urls_range"]
        urls = [source["urls_pattern"].format(i) for i in range(start, end)]
    
    passages = []
    for url in urls:
        html = fetch_url(url)
        if not html:
            continue
        text = html_to_text(html)
        chunks = split_into_passages(text, father, work)
        for chunk in chunks:
            passages.append((father, work, chunk, date, src))
        time.sleep(FETCH_DELAY)
    
    return passages


def ingest_ldysinger_source(source):
    """Fetch bilingual source from ldysinger.com, extract original + English."""
    father = source["father"]
    work = source["work"]
    date = source["date"]
    src = source["source"]
    lang = source.get("lang", "greek")
    
    html = fetch_url(source["url"])
    if not html:
        return []
    
    text = html_to_text(html)
    chunks = split_into_passages(text, father, work)
    
    passages = []
    for chunk in chunks:
        passages.append((father, work, chunk, date, src, lang))
    
    return passages


def ingest_all():
    """Main ingestion pipeline."""
    conn = get_db()
    total_inserted = 0
    
    # 1. New Advent sources (English)
    print("=== Ingesting New Advent sources ===", flush=True)
    for i, source in enumerate(NEWADVENT_SOURCES):
        print(f"  [{i+1}/{len(NEWADVENT_SOURCES)}] {source['father']} — {source['work']}...", flush=True)
        passages = ingest_newadvent_source(source)
        
        rows = [(
            source["covers"].split(",")[0],  # book (first if multiple)
            0, 0,  # chapter=0, verse=0 (unclassified, will be assigned by LLM)
            p[0], p[1], p[2], p[3], p[4]
        ) for p in passages]
        
        if rows:
            conn.executemany("""
                INSERT OR IGNORE INTO patristic
                (book, chapter, verse_num, father, work, text, date_approx, source_collection)
                VALUES (?,?,?,?,?,?,?,?)
            """, rows)
            conn.commit()
            total_inserted += len(rows)
            print(f"    → {len(rows)} passages inserted", flush=True)
    
    # 2. ldysinger.com sources (bilingual)
    print("\n=== Ingesting ldysinger.com sources ===", flush=True)
    for i, source in enumerate(LDYSINGER_SOURCES):
        print(f"  [{i+1}/{len(LDYSINGER_SOURCES)}] {source['father']} — {source['work']}...", flush=True)
        passages = ingest_ldysinger_source(source)
        
        rows = [(
            source["covers"].split(",")[0],
            0, 0,
            p[0], p[1], p[2], '', p[5], p[3], p[4]
        ) for p in passages]
        
        if rows:
            conn.executemany("""
                INSERT OR IGNORE INTO patristic
                (book, chapter, verse_num, father, work, text, text_original, original_lang, date_approx, source_collection)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, rows)
            conn.commit()
            total_inserted += len(rows)
            print(f"    → {len(rows)} passages inserted", flush=True)
    
    conn.close()
    print(f"\n=== TOTAL: {total_inserted:,} passages ingested ===", flush=True)
    return total_inserted


if __name__ == "__main__":
    t0 = time.time()
    n = ingest_all()
    print(f"Done in {time.time()-t0:.0f}s — {n:,} passages ready for classification.", flush=True)
