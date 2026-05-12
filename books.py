"""Canonical book resolution — maps any name/alias/ID to the DB canonical name."""
import unicodedata

# Canonical book list: ID -> (db_name, [aliases including spanish, abbreviations, etc.])
# IDs 1-66 = Protestant canon, 67+ = deuterocanonical/extra
BOOKS: dict[int, tuple[str, list[str]]] = {
    # Torah / Pentateuch
    1: ("Genesis", ["Gen", "Gn", "Génesis", "Genesis", "Γένεσις", "Genèse", "Liber Genesis"]),
    2: ("Exodus", ["Exod", "Ex", "Éxodo", "Exodo", "Ἔξοδος", "Exode", "Liber Exodus"]),
    3: ("Leviticus", ["Lev", "Lv", "Levítico", "Levitico", "Λευιτικόν", "Lévitique", "Liber Leviticus"]),
    4: ("Numbers", ["Num", "Nm", "Números", "Numeros", "Ἀριθμοί", "Nombres", "Liber Numeri", "Numeri"]),
    5: ("Deuteronomy", ["Deut", "Dt", "Deuteronomio", "Δευτερονόμιον", "Deutéronome", "Liber Deuteronomii"]),
    # Historical
    6: ("Joshua", ["Josh", "Jos", "Josué", "Josue", "Ἰησοῦς τοῦ Ναυή", "Josué", "Liber Iosue"]),
    7: ("Judges", ["Judg", "Jdg", "Jue", "Jueces", "Κριταί", "Juges", "Liber Iudicum"]),
    8: ("Ruth", ["Rut", "Rt", "Ῥούθ", "Liber Ruth"]),
    9: ("1 Samuel", ["1Sam", "1 Sam", "I Samuel", "1S", "Α΄ Σαμουήλ", "1 Samuel", "Liber I Samuelis"]),
    10: ("2 Samuel", ["2Sam", "2 Sam", "II Samuel", "2S", "Β΄ Σαμουήλ", "2 Samuel", "Liber II Samuelis"]),
    11: ("1 Kings", ["1Kgs", "1 Kgs", "I Kings", "1 Reyes", "1Reyes", "1Re", "1R", "Α΄ Βασιλειῶν", "1 Rois", "Liber I Regum"]),
    12: ("2 Kings", ["2Kgs", "2 Kgs", "II Kings", "2 Reyes", "2Reyes", "2Re", "2R", "Β΄ Βασιλειῶν", "2 Rois", "Liber II Regum"]),
    13: ("1 Chronicles", ["1Chr", "1 Chr", "I Chronicles", "1 Crónicas", "1Cronicas", "1Crónicas", "1Cr", "Α΄ Παραλειπομένων", "1 Chroniques", "Liber I Paralipomenon"]),
    14: ("2 Chronicles", ["2Chr", "2 Chr", "II Chronicles", "2 Crónicas", "2Cronicas", "2Crónicas", "2Cr", "Β΄ Παραλειπομένων", "2 Chroniques", "Liber II Paralipomenon"]),
    15: ("Ezra", ["Esd", "Esdras", "Ἔσδρας", "Esdras", "Liber Esdrae"]),
    16: ("Nehemiah", ["Neh", "Nehemías", "Nehemias", "Νεεμίας", "Néhémie", "Liber Nehemiae"]),
    17: ("Esther", ["Esth", "Est", "Ester", "Ἐσθήρ", "Esther", "Liber Esther"]),
    # Poetic
    18: ("Job", ["Ἰώβ", "Liber Iob"]),
    19: ("Psalms", ["Ps", "Pss", "Sal", "Salmos", "Salmo", "Ψαλμοί", "Psaumes", "Liber Psalmorum", "Psalmi"]),
    20: ("Proverbs", ["Prov", "Pr", "Proverbios", "Παροιμίαι", "Proverbes", "Liber Proverbiorum"]),
    21: ("Ecclesiastes", ["Eccl", "Ec", "Eclesiastés", "Eclesiastes", "Qoh", "Qohelet", "Ἐκκλησιαστής", "Ecclésiaste", "Liber Ecclesiastes"]),
    22: ("Song of Solomon", ["Song", "Cant", "Cantar", "Cantar de los Cantares", "Cantares", "SOS", "Ἆσμα Ἀσμάτων", "Cantique des Cantiques", "Canticum Canticorum"]),
    # Major Prophets
    23: ("Isaiah", ["Isa", "Is", "Isaías", "Isaias", "Ἠσαΐας", "Ésaïe", "Isaïe", "Liber Isaiae"]),
    24: ("Jeremiah", ["Jer", "Jr", "Jeremías", "Jeremias", "Ἱερεμίας", "Jérémie", "Liber Ieremiae"]),
    25: ("Lamentations", ["Lam", "Lamentaciones", "Θρῆνοι", "Lamentations", "Liber Lamentationum", "Threni"]),
    26: ("Ezekiel", ["Ezek", "Ez", "Ezequiel", "Ἰεζεκιήλ", "Ézéchiel", "Liber Ezechielis"]),
    27: ("Daniel", ["Dan", "Dn", "Δανιήλ", "Liber Danielis"]),
    # Minor Prophets
    28: ("Hosea", ["Hos", "Os", "Oseas", "Ὡσηέ", "Osée", "Liber Osee"]),
    29: ("Joel", ["Jl", "Ἰωήλ", "Joël", "Liber Ioel"]),
    30: ("Amos", ["Am", "Ἀμώς", "Liber Amos"]),
    31: ("Obadiah", ["Obad", "Abd", "Abdías", "Abdias", "Ὀβαδίας", "Abdias", "Liber Abdiae"]),
    32: ("Jonah", ["Jon", "Jonás", "Jonas", "Ἰωνᾶς", "Liber Ionae"]),
    33: ("Micah", ["Mic", "Mi", "Miqueas", "Μιχαίας", "Michée", "Liber Michaeae"]),
    34: ("Nahum", ["Nah", "Na", "Nahúm", "Nahum", "Ναούμ", "Liber Nahum"]),
    35: ("Habakkuk", ["Hab", "Habacuc", "Ἀμβακούμ", "Habacuc", "Liber Habacuc"]),
    36: ("Zephaniah", ["Zeph", "Sof", "Sofonías", "Sofonias", "Σοφονίας", "Sophonie", "Liber Sophoniae"]),
    37: ("Haggai", ["Hag", "Hageo", "Ἀγγαῖος", "Aggée", "Liber Aggaei"]),
    38: ("Zechariah", ["Zech", "Zac", "Zacarías", "Zacarias", "Ζαχαρίας", "Zacharie", "Liber Zachariae"]),
    39: ("Malachi", ["Mal", "Malaquías", "Malaquias", "Μαλαχίας", "Malachie", "Liber Malachiae"]),
    # NT - Gospels & Acts
    40: ("Matthew", ["Matt", "Mt", "Mateo", "Ματθαῖος", "Matthieu", "Evangelium secundum Matthaeum"]),
    41: ("Mark", ["Mrk", "Mc", "Marcos", "Μᾶρκος", "Marc", "Evangelium secundum Marcum"]),
    42: ("Luke", ["Luk", "Lc", "Lucas", "Λουκᾶς", "Luc", "Evangelium secundum Lucam"]),
    43: ("John", ["Jn", "Juan", "Ἰωάννης", "Jean", "Evangelium secundum Ioannem"]),
    44: ("Acts", ["Hch", "Hechos", "Acts of the Apostles", "Πράξεις", "Actes", "Actes des Apôtres", "Actus Apostolorum"]),
    # NT - Pauline
    45: ("Romans", ["Rom", "Ro", "Romanos", "Ῥωμαίους", "Romains", "Epistula ad Romanos"]),
    46: ("1 Corinthians", ["1Cor", "1 Cor", "I Corinthians", "1 Corintios", "1Corintios", "Α΄ Κορινθίους", "1 Corinthiens", "Epistula I ad Corinthios"]),
    47: ("2 Corinthians", ["2Cor", "2 Cor", "II Corinthians", "2 Corintios", "2Corintios", "Β΄ Κορινθίους", "2 Corinthiens", "Epistula II ad Corinthios"]),
    48: ("Galatians", ["Gal", "Gá", "Gálatas", "Galatas", "Γαλάτας", "Galates", "Epistula ad Galatas"]),
    49: ("Ephesians", ["Eph", "Ef", "Efesios", "Ἐφεσίους", "Éphésiens", "Epistula ad Ephesios"]),
    50: ("Philippians", ["Phil", "Fil", "Filipenses", "Φιλιππησίους", "Philippiens", "Epistula ad Philippenses"]),
    51: ("Colossians", ["Col", "Colosenses", "Κολοσσαεῖς", "Colossiens", "Epistula ad Colossenses"]),
    52: ("1 Thessalonians", ["1Thess", "1 Thess", "I Thessalonians", "1 Tesalonicenses", "1Tesalonicenses", "1Ts", "Α΄ Θεσσαλονικεῖς", "1 Thessaloniciens"]),
    53: ("2 Thessalonians", ["2Thess", "2 Thess", "II Thessalonians", "2 Tesalonicenses", "2Tesalonicenses", "2Ts", "Β΄ Θεσσαλονικεῖς", "2 Thessaloniciens"]),
    54: ("1 Timothy", ["1Tim", "1 Tim", "I Timothy", "1 Timoteo", "1Timoteo", "Α΄ Τιμόθεον", "1 Timothée"]),
    55: ("2 Timothy", ["2Tim", "2 Tim", "II Timothy", "2 Timoteo", "2Timoteo", "Β΄ Τιμόθεον", "2 Timothée"]),
    56: ("Titus", ["Tit", "Tito", "Τίτον", "Tite", "Epistula ad Titum"]),
    57: ("Philemon", ["Phlm", "Flm", "Filemón", "Filemon", "Φιλήμονα", "Philémon", "Epistula ad Philemonem"]),
    58: ("Hebrews", ["Heb", "He", "Hebreos", "Ἑβραίους", "Hébreux", "Epistula ad Hebraeos"]),
    # NT - General
    59: ("James", ["Jas", "Stg", "Santiago", "Ἰάκωβος", "Jacques", "Epistula Iacobi"]),
    60: ("1 Peter", ["1Pet", "1 Pet", "I Peter", "1 Pedro", "1Pedro", "Α΄ Πέτρου", "1 Pierre"]),
    61: ("2 Peter", ["2Pet", "2 Pet", "II Peter", "2 Pedro", "2Pedro", "Β΄ Πέτρου", "2 Pierre"]),
    62: ("1 John", ["1John", "1 Jn", "I John", "1 Juan", "1Juan", "Α΄ Ἰωάννου", "1 Jean"]),
    63: ("2 John", ["2John", "2 Jn", "II John", "2 Juan", "2Juan", "Β΄ Ἰωάννου", "2 Jean"]),
    64: ("3 John", ["3John", "3 Jn", "III John", "3 Juan", "3Juan", "Γ΄ Ἰωάννου", "3 Jean"]),
    65: ("Jude", ["Jud", "Judas", "Ἰούδας", "Epistula Iudae"]),
    66: ("Revelation", ["Rev", "Ap", "Apocalipsis", "Revelation of John", "Ἀποκάλυψις", "Apocalypse", "Liber Apocalypsis"]),
    # Deuterocanonical
    67: ("Tobit", ["Tob", "TobS", "TobBA", "Tobías", "Tobias", "Τωβίτ", "Tobie", "Liber Tobiae"]),
    68: ("Judith", ["Jdt", "Judit", "Ἰουδίθ", "Liber Iudith"]),
    69: ("Wisdom", ["Wis", "Sab", "Sabiduría", "Sabiduria", "Wisdom of Solomon", "Σοφία Σαλομῶντος", "Sagesse", "Liber Sapientiae"]),
    70: ("Sirach", ["Sir", "Eclesiástico", "Eclesiastico", "Ecclesiasticus", "Σοφία Σειράχ", "Siracide", "Ecclésiastique", "Liber Ecclesiasticus"]),
    71: ("Baruch", ["Bar", "Baruc", "Βαρούχ", "Liber Baruch"]),
    72: ("1 Maccabees", ["1Macc", "1 Macc", "I Maccabees", "1 Macabeos", "1Macabeos", "Α΄ Μακκαβαίων", "1 Maccabées", "Liber I Maccabaeorum"]),
    73: ("2 Maccabees", ["2Macc", "2 Macc", "II Maccabees", "2 Macabeos", "2Macabeos", "Β΄ Μακκαβαίων", "2 Maccabées", "Liber II Maccabaeorum"]),
    74: ("3 Maccabees", ["3Macc", "3 Macc", "III Maccabees", "3 Macabeos", "3Macabeos", "Γ΄ Μακκαβαίων", "3 Maccabées"]),
    75: ("4 Maccabees", ["4Macc", "4 Macc", "IV Maccabees", "4 Macabeos", "4Macabeos", "Δ΄ Μακκαβαίων", "4 Maccabées"]),
    # Extra
    76: ("Prayer of Manasses", ["PrMan", "Oración de Manasés", "Oracion de Manases", "Προσευχὴ Μανασσῆ", "Prière de Manassé", "Oratio Manassae"]),
    77: ("Psalms of Solomon", ["PsSol", "Salmos de Salomón", "Salmos de Salomon", "Ψαλμοὶ Σαλομῶντος", "Psaumes de Salomon"]),
    78: ("Odes", ["Odas", "Ὠδαί"]),
    79: ("Epistle of Jeremiah", ["EpJer", "Epístola de Jeremías", "Epistola de Jeremias", "Ἐπιστολὴ Ἱερεμίου", "Lettre de Jérémie", "Epistula Ieremiae"]),
    # Apostolic Fathers
    80: ("1 Clement", ["1Clem", "1 Clemente", "Α΄ Κλήμεντος", "1 Clément"]),
    81: ("2 Clement", ["2Clem", "2 Clemente", "Β΄ Κλήμεντος", "2 Clément"]),
    82: ("Didache", ["Did", "Didajé", "Didaje", "Διδαχή", "Didachè"]),
    83: ("Epistle of Barnabas", ["Barn", "Bernabé", "Bernabe", "Epístola de Bernabé", "Ἐπιστολὴ Βαρνάβα", "Épître de Barnabé", "Epistula Barnabae"]),
    84: ("Shepherd of Hermas", ["Herm", "Pastor de Hermas", "Ποιμὴν τοῦ Ἑρμᾶ", "Pasteur d'Hermas", "Pastor Hermae"]),
}

def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# Build lookup: normalized_alias -> db_name
_LOOKUP: dict[str, str] = {}
for _id, (db_name, aliases) in BOOKS.items():
    for name in [db_name] + aliases:
        _LOOKUP[_strip_accents(name).lower()] = db_name

def resolve_book(name_or_id) -> str | None:
    """Resolve any book name, alias, or numeric ID to the canonical DB name.
    Returns None if not found."""
    # Numeric ID
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        entry = BOOKS.get(int(name_or_id))
        return entry[0] if entry else None
    # String lookup
    key = _strip_accents(str(name_or_id)).strip().lower()
    return _LOOKUP.get(key)

def get_all_db_names(book: str) -> list[str]:
    """Given a resolved canonical name, return all DB variants to try (for tables with inconsistent naming)."""
    key = _strip_accents(book).lower()
    for _id, (db_name, aliases) in BOOKS.items():
        if _strip_accents(db_name).lower() == key:
            return [db_name] + aliases
    return [book]
