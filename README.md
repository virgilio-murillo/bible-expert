# Bible Expert MCP Server

A comprehensive biblical research MCP (Model Context Protocol) server providing 12 tools for multilingual text access, critical apparatus, patristic commentary, Dead Sea Scrolls, and authenticity analysis.

## Features

- **6 Bible versions**: MorphGNT (Greek NT), LXX (Septuagint), WLC (Hebrew), RVR1960 (Spanish), YLT (English), Vulgate (Latin)
- **997 Dead Sea Scrolls** with Hebrew text
- **Apostolic Fathers** in Greek (Didache, 1-2 Clement, Ignatius, Polycarp, Barnabas, Hermas)
- **64,872 cross-references** with confidence scoring
- **~49,000 patristic passages** from ANF/NPNF (37 volumes), indexed by verse
- **Critical apparatus** for 11 major textual variants
- **Semantic search** using multilingual embeddings (50+ languages)
- **Versification normalization** — always use RVR60/English numbering, auto-converts for LXX/Vulgate/Hebrew

## Tools

| Tool | Description |
|------|-------------|
| `verse_lookup` | Look up verse(s) by reference in any version |
| `parallel_versions` | Side-by-side comparison across translations |
| `semantic_search` | Search by meaning in any language |
| `morphology_analysis` | Word-by-word parsing (Greek/Hebrew) |
| `critical_apparatus` | Textual variants with manuscript evidence |
| `patristic_commentary` | Church Fathers commentary by verse |
| `cross_references` | Intertextual connections |
| `word_study` | Deep word analysis (Strong's + definitions) |
| `authenticity_report` | Evidence for a text's authenticity |
| `dss_lookup` | Search Dead Sea Scrolls |
| `canon_history` | Canonical history timeline |
| `text_comparison` | Compare parallel passages across traditions |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USER/bible-expert.git
cd bible-expert
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Initialize database
python ingest/init_schema.py

# Ingest local data (if you have koine-anki repo)
export KOINE_ANKI_PATH=/path/to/koine-anki
python ingest/ingest_local.py

# Download and ingest external sources
./setup.sh

# Generate semantic embeddings (~2 min)
python ingest/generate_embeddings.py

# Run the server
python server.py
```

## Usage with Claude Code / kiro-cli / any MCP client

### Claude Code (claude.ai)
Add to your MCP config:
```json
{
  "mcpServers": {
    "bible-expert": {
      "command": "python",
      "args": ["/path/to/bible-expert/server.py"]
    }
  }
}
```

### kiro-cli
```json
{
  "name": "bible-expert",
  "mcpServers": {
    "bible-tools": {
      "command": "/path/to/bible-expert/.venv/bin/python",
      "args": ["/path/to/bible-expert/server.py"]
    }
  }
}
```

### Any MCP client (stdio transport)
```bash
python server.py
```
The server communicates via JSON-RPC over stdin/stdout.

## Data Sources

| Source | License | Content |
|--------|---------|---------|
| [MorphGNT](https://github.com/morphgnt/sblgnt) | CC-BY-SA | Greek NT with morphology |
| [OpenScriptures morphhb](https://github.com/openscriptures/morphhb) | CC-BY 4.0 | Hebrew Bible (WLC) |
| [LXX-Rahlfs-1935](https://github.com/eliranwong/LXX-Rahlfs-1935) | Open | Septuagint |
| [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) | MIT | 140+ translations, cross-refs |
| [jtauber/apostolic-fathers](https://github.com/jtauber/apostolic-fathers) | CC-BY-SA 4.0 | Greek text |
| [ETCBC/dss](https://github.com/ETCBC/dss) | CC-BY-NC 4.0 | Dead Sea Scrolls |
| [gregorycrane/nicenefathers](https://github.com/gregorycrane/nicenefathers) | Public Domain | ANF/NPNF patristics |
| Strong's Greek Dictionary | Public Domain | Lexicon |

## Versification

All tools accept **RVR60/English numbering** as input. The system automatically converts when querying versions with different numbering:

- **Psalms**: LXX/Vulgate offset (Ps 23 Hebrew = Ps 22 LXX)
- **Joel**: English 3 chapters → Hebrew 4 chapters
- **Malachi**: English 4 chapters → Hebrew 3 chapters  
- **Exodus 8**: English 8:1-4 → Hebrew 7:26-29

A note is displayed when numbering differs.

## Texts in Scope

- Protocanonical (66 Protestant books)
- Deuterocanonical (Tobit, Judith, Wisdom, Sirach, Baruch, 1-2 Maccabees)
- Orthodox extended canon (3-4 Maccabees, 1 Esdras, Prayer of Manasseh, Psalm 151)
- Pseudepigrapha (1-2-3 Enoch, Jubilees, Testaments XII Patriarchs, etc.)
- Apostolic Fathers (Didache, Clement, Ignatius, Polycarp, Barnabas, Hermas)
- NT Apocrypha (Gospel of Thomas, Protoevangelium of James, etc.)
- Dead Sea Scrolls (1QS, 1QM, 1QIsaᵃ, 11QTemple, Pesharim, Hodayot, CD, 4QMMT)
- Expansions (Book of Jasher, Pseudo-Philo, Cave of Treasures)

## Requirements

- Python 3.11+
- ~300MB disk for full database with embeddings
- Optional: AWS credentials for LLM-based patristic indexing (`ingest/index_patristic_llm.py`)
