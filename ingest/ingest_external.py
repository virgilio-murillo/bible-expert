"""Ingest external data sources into the Bible Expert database."""
import csv
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
EXT = Path(__file__).parent.parent / "data" / "external"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ingest_ylt():
    """Ingest Young's Literal Translation."""
    print("Ingesting YLT...")
    path = EXT / "bible_databases/sources/en/YLT/YLT.json"
    with open(path) as f:
        data = json.load(f)
    
    conn = get_db()
    rows = []
    for book in data["books"]:
        book_name = book["name"]
        for chapter in book["chapters"]:
            ch = chapter["chapter"]
            for verse in chapter["verses"]:
                vs = verse["verse"]
                text = verse["text"]
                testament = "OT" if ch <= 39 else "NT"  # rough
                rows.append((book_name, ch, vs, "YLT", text, testament, "protocanonical", None))
    
    conn.executemany(
        "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"  YLT: {len(rows)} verses")


def ingest_apostolic_fathers():
    """Ingest Apostolic Fathers Greek texts."""
    print("Ingesting Apostolic Fathers...")
    texts_dir = EXT / "apostolic-fathers/texts"
    
    # Map filenames to book names
    book_map = {
        "001-i_clement": "1 Clement",
        "002-ii_clement": "2 Clement",
        "003-ignatius-ephesians": "Ignatius to Ephesians",
        "004-ignatius-magnesians": "Ignatius to Magnesians",
        "005-ignatius-trallians": "Ignatius to Trallians",
        "006-ignatius-romans": "Ignatius to Romans",
        "007-ignatius-philadelphians": "Ignatius to Philadelphians",
        "008-ignatius-smyrnaeans": "Ignatius to Smyrnaeans",
        "009-ignatius-polycarp": "Ignatius to Polycarp",
        "010-polycarp-philippians": "Polycarp to Philippians",
        "011-didache": "Didache",
        "012-barnabas": "Epistle of Barnabas",
        "013-shepherd": "Shepherd of Hermas",
        "014-diognetus": "Epistle to Diognetus",
    }
    
    conn = get_db()
    rows = []
    for f in sorted(texts_dir.glob("*.txt")):
        stem = f.stem
        book_name = book_map.get(stem, stem)
        
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            # Format: "chapter.verse text..."
            parts = line.split(" ", 1)
            if len(parts) < 2 or "." not in parts[0]:
                continue
            ref = parts[0]
            text = parts[1]
            try:
                ch, vs = ref.split(".")
                rows.append((book_name, int(ch), int(vs), "ApostolicFathers", text, None, "apostolic_fathers", None))
            except ValueError:
                continue
    
    conn.executemany(
        "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"  Apostolic Fathers: {len(rows)} sections")


def ingest_lxx():
    """Ingest LXX Rahlfs 1935 from CSV data."""
    print("Ingesting LXX Rahlfs...")
    lxx_dir = EXT / "LXX-Rahlfs-1935"
    
    # Find the main text file
    text_files = list(lxx_dir.glob("01_wordlist_unicode/*.csv")) or list(lxx_dir.glob("**/*verse*.csv"))
    
    # Try the versification + wordlist approach
    verse_file = lxx_dir / "08_versification" / "001_verse_c_book.csv"
    wordlist_dir = lxx_dir / "01_wordlist_unicode"
    
    if not wordlist_dir.exists():
        # Try alternative structure
        for d in lxx_dir.iterdir():
            if d.is_dir() and "word" in d.name.lower():
                wordlist_dir = d
                break
    
    conn = get_db()
    
    # Read book list from versification
    books = []
    if verse_file.exists():
        books = verse_file.read_text().strip().splitlines()
    
    # Try to find pre-assembled verse text
    assembled = list(lxx_dir.glob("**/*assembled*")) or list(lxx_dir.glob("**/LXX*.txt"))
    
    # Fallback: read word-by-word files and assemble
    rows = []
    for wf in sorted(wordlist_dir.glob("*.csv")) if wordlist_dir.exists() else []:
        book_name = wf.stem
        current_verse = {}
        
        with open(wf, encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                # Typical format: chapter, verse, word
                try:
                    ch, vs = int(row[0]), int(row[1])
                    word = row[2] if len(row) > 2 else ""
                    key = (book_name, ch, vs)
                    current_verse.setdefault(key, []).append(word)
                except (ValueError, IndexError):
                    continue
        
        for (book, ch, vs), words in current_verse.items():
            text = " ".join(words)
            rows.append((book, ch, vs, "LXX", text, "OT", "protocanonical", None))
    
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
            rows
        )
        conn.commit()
    conn.close()
    print(f"  LXX: {len(rows)} verses")


def ingest_morphhb():
    """Ingest Hebrew Bible (WLC) from OpenScriptures morphhb XML."""
    print("Ingesting Hebrew Bible (WLC)...")
    import xml.etree.ElementTree as ET
    
    morphhb_dir = EXT / "morphhb/wlc"
    conn = get_db()
    rows = []
    
    for xml_file in sorted(morphhb_dir.glob("*.xml")):
        book_name = xml_file.stem
        tree = ET.parse(xml_file)
        root = tree.getroot()
        ns = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}
        
        for verse in root.iter("{http://www.bibletechnologies.net/2003/OSIS/namespace}verse"):
            osis_id = verse.get("osisID", "")
            if not osis_id:
                continue
            # Format: "Gen.1.1"
            parts = osis_id.split(".")
            if len(parts) < 3:
                continue
            ch, vs = int(parts[1]), int(parts[2])
            
            # Collect all words in this verse
            words = []
            for w in verse.iter("{http://www.bibletechnologies.net/2003/OSIS/namespace}w"):
                if w.text:
                    words.append(w.text)
            
            if words:
                text = " ".join(words)
                rows.append((book_name, ch, vs, "WLC", text, "OT", "protocanonical", None))
    
    conn.executemany(
        "INSERT OR IGNORE INTO verses (book, chapter, verse_num, version, text, testament, canon_status, morphology) VALUES (?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"  WLC (Hebrew): {len(rows)} verses")


def ingest_authenticity_data():
    """Populate authenticity reports for key texts."""
    print("Ingesting authenticity data...")
    conn = get_db()
    
    texts = [
        ("1 Enoch", "Ethiopic Enoch, Book of Enoch", "300-100 BCE (composite)", "Scholarly consensus: 5 sections composed independently. Watchers (300 BCE), Parables (100 BCE-68 CE), Astronomical (300 BCE), Dream Visions (165 BCE), Epistle (170 BCE)", "Ge'ez (Ethiopic); original Aramaic (Watchers, Astronomical), possibly Hebrew (Epistle)", "Earliest: 4QEn (4Q201-202, 4Q204-212) — Aramaic fragments from Qumran, 200-150 BCE. Complete text only in Ge'ez manuscripts (15th-18th c.). Greek fragments: P.Oxy 2069 (Chester Beatty), Codex Panopolitanus (6th c.)", "Jude 14-15 quotes 1 En 1:9 directly. Tertullian (De Cultu Fem. 1.3) treats it as Scripture. Origen (De Princ. 4.35) cites it. Clement of Alexandria (Eclogae Proph. 2.1) quotes it. Augustine rejects it (City of God 15.23).", "15 Aramaic fragments found at Qumran (Caves 1, 2, 4, 7). All sections except Parables attested. This proves pre-Christian composition and widespread use in Second Temple Judaism.", "Canonical: Ethiopian Orthodox Church. Rejected: all other traditions. Jerome (Ep. 107) explicitly excludes it. Hilary of Poitiers lists it among apocrypha. The Gelasian Decree (6th c.) lists it as rejected.", "1) Parables (chs 37-71) absent from Qumran — possibly Christian-era composition. 2) 'Son of Man' christology debate. 3) Relationship to Daniel 7. 4) Whether Jude's citation implies canonicity.", "Parables section (chs 37-71) may contain Christian interpolations. Chapter 105 is likely a later addition. The Noah fragments (chs 6-11, 54-55, 60, 65-69) may be from a separate 'Book of Noah'.", "1 Enoch is a composite work spanning 200+ years. Its Aramaic sections are firmly pre-Christian (Qumran evidence). It profoundly influenced NT angelology, eschatology, and messianism. The Parables remain debated."),
        ("Gospel of Thomas", "Evangelium Thomae, EvTh, GTh", "50-140 CE (debated)", "Three positions: (1) Early (50-70 CE) — independent of Synoptics, preserving early Jesus tradition. (2) Mid (100-120 CE) — knows Synoptics but reworks them. (3) Late (140+ CE) — Gnostic composition. Majority: 100-140 CE for final form, with some sayings possibly earlier.", "Coptic (Nag Hammadi codex II); original likely Greek", "Greek fragments: P.Oxy 1 (c. 200 CE), P.Oxy 654 (c. 250 CE), P.Oxy 655 (c. 200 CE). Complete Coptic: Nag Hammadi Codex II (c. 340 CE, discovered 1945).", "Hippolytus (Ref. 5.7.20) mentions it. Origen (Hom. Luc. 1) lists it among rejected gospels. Eusebius (HE 3.25.6) classifies it as heretical. Cyril of Jerusalem (Catech. 4.36) warns against it.", "Nag Hammadi discovery (1945) provided complete text. P.Oxy fragments prove Greek circulation in Egypt by 200 CE.", "Never canonical in any tradition. Listed in Gelasian Decree as rejected. Stichometry of Nicephorus lists it among NT apocrypha (1,300 lines).", "1) Independence from Synoptics vs dependence. 2) Gnostic or pre-Gnostic? 3) Relationship to Q source. 4) Whether it preserves authentic Jesus sayings not in canonical gospels.", "Saying 114 (misogynistic) likely a later addition. Some scholars see the prologue and framework as secondary. The Coptic version may differ from the Greek original.", "Thomas is our most important non-canonical gospel. It preserves 114 sayings of Jesus, some paralleling the Synoptics, others unique. Its independence from canonical gospels remains the central debate."),
        ("Didache", "Teaching of the Twelve Apostles, Didachē", "50-120 CE", "Most scholars: 70-100 CE for final form. The 'Two Ways' section (chs 1-6) may be pre-Christian Jewish material. Liturgical sections (chs 7-10) reflect very early practice. Church order (chs 11-15) shows transition from itinerant to settled ministry.", "Greek", "Codex Hierosolymitanus (1056 CE, discovered 1873 by Bryennios). P.Oxy 1782 (4th c., fragment of chs 1-2). Coptic fragment (British Museum, 5th c.). Georgian version (partial).", "Clement of Alexandria (Strom. 1.20) may allude to it. Eusebius (HE 3.25.4) lists it among 'disputed' books. Athanasius (Ep. Fest. 39) recommends it for catechesis but not as Scripture. Didascalia Apostolorum (3rd c.) incorporates it.", "P.Oxy 1782 confirms early Egyptian circulation.", "Almost canonical: listed in some early canon lists (Stichometry of Nicephorus, Codex Claromontanus). Used for catechesis in Alexandria. Never formally canonized.", "1) Relationship to Matthew (esp. chs 5-7). 2) Whether eucharistic prayers (chs 9-10) are pre-Pauline. 3) Jewish or Christian origin of Two Ways. 4) Composite document or unified composition.", "Chapter 1:3b-2:1 ('evangelical section') is likely interpolated from Matthew/Luke. Chapter 16 (eschatology) may be a later addition.", "The Didache is arguably the most important early Christian document outside the NT. It provides our earliest evidence for baptismal practice, eucharistic liturgy, and church governance."),
        ("Book of Jasher", "Sefer haYashar, Liber Iusti", "11th-12th century CE (medieval compilation)", "The surviving text is a medieval Hebrew composition, likely from 11th-12th century Spain or Italy. It draws on earlier midrashic traditions (Genesis Rabbah, Pirke de-Rabbi Eliezer, Targumim) but is NOT the book mentioned in Joshua 10:13 and 2 Samuel 1:18. First printed: Naples, 1625.", "Hebrew (medieval)", "Earliest manuscript: Naples 1625 printing. No ancient manuscripts exist. The book mentioned in Joshua 10:13 is lost and unrelated to this text.", "No patristic citations of this text (it didn't exist yet). The biblical references (Jos 10:13, 2 Sam 1:18) refer to a different, lost work — likely a collection of ancient Hebrew poetry.", "None. No Dead Sea Scrolls fragments. No ancient manuscript evidence.", "Not canonical in any tradition. Sometimes confused with the lost biblical 'Book of Jasher' due to the shared name. Popular in some Messianic Jewish and Ethiopian Christian circles.", "1) Relationship to the lost biblical Jasher. 2) Date of composition (11th vs 13th century). 3) Sources used (which midrashim). 4) Whether any authentic ancient traditions are preserved.", "The entire text is a medieval composition. It is NOT the book referenced in Joshua and Samuel. However, it preserves midrashic traditions that may reflect older oral material.", "A medieval Hebrew narrative expanding Genesis-Joshua with dramatic details. Despite its name, it is unrelated to the ancient 'Book of Jasher' cited in the Bible. Valuable as a compilation of Jewish legendary traditions but not an ancient text."),
        ("Shepherd of Hermas", "Pastor Hermae", "100-160 CE", "Most scholars: composed in stages. Visions 1-4 (~100 CE), Vision 5 + Mandates + Similitudes 1-8 (~130-140 CE), Similitude 9 (~140-150 CE). Rome.", "Greek (original); Latin, Ethiopic, Coptic translations", "P.Mich. 130 (3rd c., earliest). P.Oxy 3528 (3rd c.). Codex Sinaiticus (4th c., includes Hermas after Revelation). P.Bodmer 38 (4th c.). Codex Athous (15th c., complete Greek).", "Irenaeus (Adv. Haer. 4.20.2) cites it as Scripture. Clement of Alexandria (Strom. 1.29) quotes it frequently. Origen (De Princ. 4.11) considers it 'divinely inspired'. Tertullian (De Pud. 10) initially accepts then rejects it. Eusebius (HE 3.3.6) reports it was read publicly in churches.", "Included in Codex Sinaiticus (4th c.) — one of our oldest complete Bibles. P.Mich. 130 proves wide 3rd-century circulation.", "Almost canonical. Included in Codex Sinaiticus. Muratorian Fragment (~170 CE) says it may be read but not publicly in church. Athanasius (Ep. Fest. 39) lists it for catechetical reading. Rejected by Gelasian Decree.", "1) Single author or composite? 2) Identity of Hermas (the Hermas of Romans 16:14?). 3) Relationship to Roman church structure. 4) Theology of post-baptismal repentance (one chance only).", "Similitude 9 appears to be a later expansion. Some scholars see Vision 5 as a secondary bridge between the Visions and Mandates.", "One of the most popular Christian texts of the 2nd-4th centuries. Its inclusion in Codex Sinaiticus shows it was treated as near-canonical. Important for understanding early Roman Christianity and penitential theology."),
        ("Jubilees", "Little Genesis, Leptogenesis", "160-150 BCE", "Firmly dated to ~160-150 BCE based on: (1) knowledge of 1 Enoch Astronomical Book, (2) Maccabean-era concerns about calendar and law, (3) 15 copies at Qumran spanning 100 BCE-50 CE.", "Hebrew (original); complete only in Ge'ez", "15 fragmentary manuscripts from Qumran (4Q216-228, 1Q17-18, 2Q19-20, 3Q5, 11Q12). Complete text only in Ge'ez (Ethiopian). Latin fragments (partial). Syriac fragments.", "Epiphanius (Panarion 39.6) mentions it. No major Church Father treats it as Scripture (except Ethiopian tradition). Damascus Document (CD 16:3-4) cites it as authoritative.", "15 copies at Qumran — more than most biblical books. This proves it was authoritative for the Qumran community. The solar calendar of Jubilees matches the Qumran calendar.", "Canonical: Ethiopian Orthodox Church. Authoritative at Qumran. Rejected by rabbinic Judaism and all other Christian traditions.", "1) Relationship to Genesis (rewriting vs commentary). 2) Sectarian or mainstream? 3) Influence on Qumran calendar. 4) Whether it influenced the NT (Galatians, Hebrews).", "Some scholars identify later additions in chapters 23 and 50. The angelology sections may draw on earlier Enochic material.", "Jubilees is a major Second Temple text that rewrites Genesis-Exodus with a 364-day solar calendar and strict halakhic interpretation. Its 15 Qumran copies prove its importance. Canonical only in Ethiopia."),
    ]
    
    conn.executemany(
        "INSERT OR IGNORE INTO authenticity (name, alt_names, date_composition, date_consensus, original_language, earliest_manuscripts, patristic_citations, archaeological_evidence, canon_status_detail, scholarly_debates, interpolations, summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        texts
    )
    conn.commit()
    conn.close()
    print(f"  Authenticity: {len(texts)} reports")


def rebuild_fts():
    """Rebuild FTS5 index."""
    print("Rebuilding FTS5 index...")
    conn = get_db()
    conn.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    print("  FTS5 index rebuilt.")


if __name__ == "__main__":
    ingest_ylt()
    ingest_apostolic_fathers()
    ingest_lxx()
    ingest_morphhb()
    ingest_authenticity_data()
    rebuild_fts()
    print("\nDone! External data ingested.")
