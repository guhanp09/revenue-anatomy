PYTHON ?= python3

.PHONY: run app test lint verify
run:
	revenue-anatomy run
app:
	streamlit run app.py --server.port 8515
test:
	$(PYTHON) -m pytest -q
lint:
	$(PYTHON) -m ruff check src tests
verify: test lint
	$(PYTHON) scripts/verify_artifacts.py
