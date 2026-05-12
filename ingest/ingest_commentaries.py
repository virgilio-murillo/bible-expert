"""Ingest Greek exegetical commentaries (Robertson's Word Pictures, Vincent's Word Studies)
from StudyLight.org (public domain texts).

Creates a 'commentaries' table with verse-level commentary data.
"""
import sqlite3, re, time
from pathlib import Path
from urllib.request import urlopen, Request

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"

# Commentary sources: (code, name, url_pattern)
SOURCES = [
    ("rwp", "Robertson's Word Pictures", "https://www.studylight.org/commentaries/eng/rwp/{book}-{chapter}.html"),
    ("vws", "Vincent's Word Studies", "https://www.studylight.org/commentaries/eng/vnt/{book}-{chapter}.html"),
]

# Book name mapping for URLs
BOOK_URLS = {
    "Matthew": "matthew", "Mark": "mark", "Luke": "luke", "John": "john",
    "Acts": "acts", "Romans": "romans", "1 Corinthians": "1-corinthians",
    "2 Corinthians": "2-corinthians", "Galatians": "galatians",
    "Ephesians": "ephesians", "Philippians": "philippians",
    "Colossians": "colossians", "1 Thessalonians": "1-thessalonians",
    "2 Thessalonians": "2-thessalonians", "1 Timothy": "1-timothy",
    "2 Timothy": "2-timothy", "Titus": "titus", "Philemon": "philemon",
    "Hebrews": "hebrews", "James": "james", "1 Peter": "1-peter",
    "2 Peter": "2-peter", "1 John": "1-john", "2 John": "2-john",
    "3 John": "3-john", "Jude": "jude", "Revelation": "revelation",
}


def fetch_page(url):
    """Fetch a page with proper headers."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Bible study tool)"})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    Error fetching {url}: {e}", flush=True)
        return ""


def parse_commentary(html):
    """Parse verse-level commentary from StudyLight HTML."""
    verses = {}
    # Split by verse headers
    parts = re.split(r'<h3 class="commentaries-entry-number"><a name="verse-(\d+)"', html)
    for i in range(1, len(parts), 2):
        verse_num = int(parts[i])
        content = parts[i + 1] if i + 1 < len(parts) else ""
        # Get content after the closing </h3> tag
        content = re.sub(r'^[^>]*>[^>]*></h3>', '', content, count=1)
        # Cut at next major section or footer
        content = re.split(r'<h3 class="commentaries-entry-number"|return to|Copyright Statement|<div class="footer|<div class="menubar', content)[0]
        # Clean HTML but preserve Greek spans
        # Convert Greek spans to markers
        content = re.sub(r'<span[^>]*LANG="el-GR"[^>]*>(.*?)</span>', r'⟨\1⟩', content, flags=re.DOTALL)
        content = re.sub(r"<span[^>]*class='_800000'[^>]*>(.*?)</span>", r'\1', content, flags=re.DOTALL)
        # Remove other HTML tags but keep structure
        content = re.sub(r'</?[Bb]>', '', content)
        content = re.sub(r'</?[Ii]>', '', content)
        content = re.sub(r'<span[^>]*scriptRef[^>]*>(.*?)</span>', r'[\1]', content, flags=re.DOTALL)
        content = re.sub(r'<[^>]+>', ' ', content)
        # Clean whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        # Restore Greek markers to HTML
        content = re.sub(r'⟨(.*?)⟩', r'<span style="font-family:serif;color:#1b5e20">\1</span>', content)
        if len(content) > 20:
            verses[verse_num] = content
    return verses


def ingest_chapter(db, book, chapter, source_code, source_name, url_template):
    """Ingest commentary for a single chapter."""
    book_url = BOOK_URLS.get(book)
    if not book_url:
        return 0
    url = url_template.format(book=book_url, chapter=chapter)
    html = fetch_page(url)
    if not html:
        return 0
    verses = parse_commentary(html)
    for verse_num, text in verses.items():
        db.execute("""INSERT OR REPLACE INTO commentaries
            (book, chapter, verse_num, source, source_name, text)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (book, chapter, verse_num, source_code, source_name, text))
    return len(verses)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--book", required=True, help="Book name (e.g. 'John')")
    p.add_argument("--chapters", type=int, help="Number of chapters to ingest")
    args = p.parse_args()

    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS commentaries (
        book TEXT,
        chapter INTEGER,
        verse_num INTEGER,
        source TEXT,
        source_name TEXT,
        text TEXT,
        PRIMARY KEY (book, chapter, verse_num, source)
    )""")
    db.commit()

    # Determine chapter count
    max_ch = args.chapters or db.execute(
        "SELECT MAX(chapter) FROM verses WHERE book=?", (args.book,)
    ).fetchone()[0] or 1

    total = 0
    for source_code, source_name, url_template in SOURCES:
        print(f"\n{source_name}:", flush=True)
        for ch in range(1, max_ch + 1):
            count = ingest_chapter(db, args.book, ch, source_code, source_name, url_template)
            total += count
            print(f"  Ch.{ch}: {count} verses", flush=True)
            db.commit()
            time.sleep(1)  # Be polite

    print(f"\nDone. Total verse commentaries: {total}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
