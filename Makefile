PYTHON ?= python3

.PHONY: metrics-scimago-fetch metrics-update metrics-update-all metrics-check

metrics-scimago-fetch:
	./scripts/biblio/fetch_scimago_csv.sh

metrics-update:
	$(PYTHON) scripts/biblio/metrics_update.py

metrics-update-all: metrics-scimago-fetch metrics-update

metrics-check:
	$(PYTHON) scripts/biblio/metrics_update.py --offline --dry-run
	bundle exec jekyll build
