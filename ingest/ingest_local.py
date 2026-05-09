"""Ingest existing local data into the Bible Expert database.

Sources:
- /Users/murivirg/work/anki/koine-anki/data/nt-morphgnt/ (27 NT books)
- /Users/murivirg/work/anki/koine-anki/data/es_rvr.json (RVR1960)
- /Users/murivirg/work/anki/koine-anki/data/strongs_greek.xml (Strong's)
"""
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
KOINE_DATA = Path(os.environ.get("KOINE_ANKI_PATH", "../koine-anki")) / "data"

# MorphGNT book mapping: filename prefix -> book name
MORPHGNT_BOOKS = {
    "61": "Matthew", "62": "Mark", "63": "Luke", "64": "John", "65": "Acts",
    "66": "Romans", "67": "1 Corinthians", "68": "2 Corinthians", "69": "Galatians",
    "70": "Ephesians", "71": "Philippians", "72": "Colossians", "73": "1 Thessalonians",
    "74": "2 Thessalonians", "75": "1 Timothy", "76": "2 Timothy", "77": "Titus",
    "78": "Philemon", "79": "Hebrews", "80": "James", "81": "1 Peter",
    "82": "2 Peter", "83": "1 John", "84": "2 John", "85": "3 John",
    "86": "Jude", "87": "Revelation",
}


def ingest_morphgnt():
    """Ingest MorphGNT data as both verse text and morphology."""
    print("Ingesting MorphGNT...")
    conn = sqlite3.connect(str(DB_PATH))
    morphgnt_dir = KOINE_DATA / "nt-morphgnt"
    
    verse_texts = {}  # (book, ch, vs) -> list of words
    morph_rows = []
    
    for f in sorted(morphgnt_dir.glob("*-morphgnt.txt")):
        prefix = f.name.split("-")[0]
        book = MORPHGNT_BOOKS.get(prefix)
        if not book:
            continue
        
        word_pos = 0
        current_verse = None
        
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            
            # MorphGNT format: BCVV morph_code text word norm lemma
            ref = parts[0]  # e.g. "010101" = book01 ch01 vs01
            ch = int(ref[2:4])
            vs = int(ref[4:6])
            
            key = (book, ch, vs)
            if key != current_verse:
                current_verse = key
                word_pos = 0
            word_pos += 1
            
            morph_code = parts[1]
            word = parts[3]  # normalized form
            lemma = parts[5] if len(parts) > 5 else ""
            
            verse_texts.setdefault(key, []).append(word)
            morph_rows.append((book, ch, vs, "MorphGNT", word_pos, word, lemma, morph_code, None, None))
    
    # Insert verses
    verse_rows = [(book, ch, vs, "MorphGNT", " ".join(words), "NT", "protocanonical", None)
                  for (book, ch, vs), words in verse_texts.items()]
    
    conn.executemany(
        "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
        verse_rows
    )
    
    # Insert morphology
    conn.executemany(
        "INSERT INTO morphology (book, chapter, verse_num, version, word_pos, word, lemma, morph_code, gloss, strongs) VALUES (?,?,?,?,?,?,?,?,?,?)",
        morph_rows
    )
    
    conn.commit()
    conn.close()
    print(f"  MorphGNT: {len(verse_rows)} verses, {len(morph_rows)} words")


def ingest_rvr1960():
    """Ingest RVR1960 from es_rvr.json."""
    print("Ingesting RVR1960...")
    conn = sqlite3.connect(str(DB_PATH))
    rvr_path = KOINE_DATA / "es_rvr.json"
    
    with open(rvr_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    
    rows = []
    for book_data in data:
        book_name = book_data.get("name") or book_data.get("abbrev", "")
        chapters = book_data.get("chapters", [])
        testament = "OT" if _is_ot(book_name) else "NT"
        
        for ch_idx, chapter_verses in enumerate(chapters, 1):
            for vs_idx, text in enumerate(chapter_verses, 1):
                if text:
                    rows.append((book_name, ch_idx, vs_idx, "RVR1960", text, testament, "protocanonical", None))
    
    conn.executemany(
        "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"  RVR1960: {len(rows)} verses")


def ingest_strongs():
    """Ingest Strong's Greek dictionary."""
    print("Ingesting Strong's Greek...")
    conn = sqlite3.connect(str(DB_PATH))
    strongs_path = KOINE_DATA / "strongs_greek.xml"
    
    tree = ET.parse(strongs_path)
    root = tree.getroot()
    rows = []
    
    for entry in root.iter("entry"):
        strongs = entry.get("strongs") or entry.findtext("strongs") or ""
        if not strongs.startswith("G"):
            strongs = "G" + strongs
        
        lemma = entry.findtext("greek") or entry.get("unicode") or ""
        gloss = entry.findtext("kjv_def") or entry.findtext("strongs_def") or ""
        definition = entry.findtext("strongs_def") or ""
        etymology = entry.findtext("derivation") or ""
        
        if lemma or gloss:
            rows.append((strongs, lemma, gloss[:200], definition[:500], etymology[:300], None, "NT", None))
    
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon (strongs, lemma, gloss, definition, etymology, frequency, corpus, root) VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"  Strong's: {len(rows)} entries")


OT_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther",
    "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    # Spanish names
    "Génesis", "Éxodo", "Levítico", "Números", "Deuteronomio",
    "Josué", "Jueces", "Rut", "1 Samuel", "2 Samuel", "1 Reyes", "2 Reyes",
    "1 Crónicas", "2 Crónicas", "Esdras", "Nehemías", "Ester",
    "Salmos", "Proverbios", "Eclesiastés", "Cantares",
    "Isaías", "Jeremías", "Lamentaciones", "Ezequiel", "Daniel",
    "Oseas", "Amós", "Abdías", "Jonás", "Miqueas",
    "Nahúm", "Habacuc", "Sofonías", "Hageo", "Zacarías", "Malaquías",
}

def _is_ot(book: str) -> bool:
    return book in OT_BOOKS


def rebuild_fts():
    """Rebuild FTS5 index."""
    print("Rebuilding FTS5 index...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    print("  FTS5 index rebuilt.")


if __name__ == "__main__":
    ingest_morphgnt()
    ingest_rvr1960()
    ingest_strongs()
    rebuild_fts()
    print("\nDone! All local data ingested.")
