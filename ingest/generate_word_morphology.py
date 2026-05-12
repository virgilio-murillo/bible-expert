"""Generate morphological decomposition for NT Greek lemmas.

For each lemma, produces a structured breakdown:
- prefix (if any): preposition or prefix with meaning
- root: the core root with meaning
- suffix (if any): derivational suffix with function
- ending: grammatical ending with parsing info

Uses Bedrock Claude in batches.
"""
import sqlite3, json, time, unicodedata
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bible.db"
BATCH_SIZE = 40


def get_lemmas_needing_decomposition(db):
    """Get lemmas that don't have decomposition yet."""
    all_lemmas = db.execute("""
        SELECT DISTINCT m.lemma, m.morph_code, m.strongs, m.gloss
        FROM morphology m
        WHERE m.version='MorphGNT' AND length(m.lemma) >= 4
        GROUP BY m.lemma
    """).fetchall()

    existing = set()
    try:
        existing = set(r[0] for r in db.execute("SELECT lemma FROM word_morphology").fetchall())
    except Exception:
        pass

    return [(r[0], r[1], r[2], r[3]) for r in all_lemmas if r[0] not in existing]


def batch_decompose(batch):
    """Use Bedrock to decompose a batch of Greek words."""
    import boto3
    from botocore.config import Config
    client = boto3.client("bedrock-runtime", region_name="us-east-1",
                          config=Config(read_timeout=120, retries={"max_attempts": 3}))

    words_list = "\n".join(f"- {lem} ({rmac}) [{strongs}] = {gloss}" for lem, rmac, strongs, gloss in batch)

    prompt = f"""Analyze these Koine Greek words morphologically. For each word, provide a JSON object with:
- "lemma": the word
- "prefix": object with "greek" and "meaning" (or null if no prefix)
- "root": object with "greek" and "meaning"  
- "suffix": object with "greek" and "function" (derivational suffix, or null)
- "ending": object with "greek" and "function" (grammatical ending indicating case/number/gender/tense/voice/mood)

Rules:
- prefix: prepositions (ἀπό, ἐπί, κατά, παρά, σύν, ἀντί, ὑπό, ὑπέρ, πρός, εἰς, ἐκ, μετά, περί, διά, ἀνά, πρό, ἐν) or other prefixes (εὐ-, δυσ-, ἀ-/ἀν- privative)
- root: the core semantic element
- suffix: derivational morphemes (-σις, -μα, -τής, -ία, -μός, -τός, -ικός, etc.)
- ending: the inflectional ending that shows grammar (-ω, -ομαι, -ος, -η, -ον, -εις, etc.)
- For simple words (no prefix, no suffix), just give root + ending
- Keep meanings in Spanish

Return ONLY a JSON array. No explanation.

Words:
{words_list}"""

    r = client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 8000, "temperature": 0},
    )
    text = r['output']['message']['content'][0]['text']
    start = text.find('[')
    end = text.rfind(']') + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    return []


def main():
    db = sqlite3.connect(str(DB_PATH))

    # Create table
    db.execute("""CREATE TABLE IF NOT EXISTS word_morphology (
        lemma TEXT PRIMARY KEY,
        prefix_greek TEXT,
        prefix_meaning TEXT,
        root_greek TEXT,
        root_meaning TEXT,
        suffix_greek TEXT,
        suffix_function TEXT,
        ending_greek TEXT,
        ending_function TEXT
    )""")
    db.commit()

    todo = get_lemmas_needing_decomposition(db)
    print(f"Lemmas to process: {len(todo)}", flush=True)

    total = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        print(f"  Batch {i//BATCH_SIZE + 1}/{(len(todo)-1)//BATCH_SIZE + 1} ({len(batch)} words)...", flush=True)
        try:
            results = batch_decompose(batch)
            for item in results:
                if not item.get("lemma"):
                    continue
                prefix = item.get("prefix") or {}
                root = item.get("root") or {}
                suffix = item.get("suffix") or {}
                ending = item.get("ending") or {}
                db.execute("""INSERT OR IGNORE INTO word_morphology
                    (lemma, prefix_greek, prefix_meaning, root_greek, root_meaning, suffix_greek, suffix_function, ending_greek, ending_function)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (item["lemma"],
                     prefix.get("greek", ""), prefix.get("meaning", ""),
                     root.get("greek", ""), root.get("meaning", ""),
                     suffix.get("greek", ""), suffix.get("function", ""),
                     ending.get("greek", ""), ending.get("function", "")))
                total += 1
            db.commit()
        except Exception as e:
            print(f"    Error: {e}", flush=True)
        time.sleep(0.5)

    print(f"\nDone. Total decompositions: {total}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
