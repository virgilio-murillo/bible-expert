#!/bin/bash
# Download and ingest all external data sources
set -e

DATA_DIR="data/external"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

echo "=== Downloading external sources ==="

# Bible translations + cross-references (MIT)
[ -d bible_databases ] || git clone --depth 1 https://github.com/scrollmapper/bible_databases.git

# Hebrew Bible with morphology (CC-BY 4.0)
[ -d morphhb ] || git clone --depth 1 https://github.com/openscriptures/morphhb.git

# Septuagint Rahlfs 1935
[ -d LXX-Rahlfs-1935 ] || git clone --depth 1 https://github.com/eliranwong/LXX-Rahlfs-1935.git

# Apostolic Fathers Greek (CC-BY-SA 4.0)
[ -d apostolic-fathers ] || git clone --depth 1 https://github.com/jtauber/apostolic-fathers.git

# Dead Sea Scrolls (CC-BY-NC 4.0)
[ -d dss ] || git clone --depth 1 https://github.com/ETCBC/dss.git

# Patristics ANF/NPNF (Public Domain)
[ -d nicenefathers ] || git clone --depth 1 https://github.com/gregorycrane/nicenefathers.git

cd ../..

echo ""
echo "=== Ingesting into database ==="
python ingest/init_schema.py
python ingest/ingest_external.py

echo ""
echo "=== Generating embeddings (this takes ~2 minutes) ==="
python ingest/generate_embeddings.py

echo ""
echo "=== Done! ==="
python -c "
import sqlite3
conn = sqlite3.connect('db/bible.db')
print(f'Verses: {conn.execute(\"SELECT count(*) FROM verses\").fetchone()[0]:,}')
print(f'DSS lines: {conn.execute(\"SELECT count(*) FROM dss\").fetchone()[0]:,}')
print(f'Cross-refs: {conn.execute(\"SELECT count(*) FROM cross_refs\").fetchone()[0]:,}')
print(f'Patristic: {conn.execute(\"SELECT count(*) FROM patristic\").fetchone()[0]:,}')
print(f'Embeddings: {conn.execute(\"SELECT count(*) FROM verse_embeddings\").fetchone()[0]:,}')
conn.close()
"
