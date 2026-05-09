# Makefile for bible-expert

.PHONY: setup run test clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e .
	chmod +x setup.sh
	.venv/bin/python ingest/init_schema.py
	@echo "Run './setup.sh' to download and ingest external data"

run:
	.venv/bin/python server.py

ingest-local:
	.venv/bin/python ingest/ingest_local.py

ingest-external:
	./setup.sh

embeddings:
	.venv/bin/python ingest/generate_embeddings.py

index-patristic:
	.venv/bin/python ingest/index_patristic_llm.py

test:
	.venv/bin/python -c "import server; print(f'{len(server.mcp._tool_manager._tools)} tools OK')"

clean:
	rm -rf db/bible.db data/external .venv __pycache__
