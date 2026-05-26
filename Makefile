PYTHON ?= python3
METRICS_ARGS ?=
SCIMAGO_INPUT ?=
SCIMAGO_ARGS :=
ifneq ($(strip $(SCIMAGO_INPUT)),)
SCIMAGO_ARGS += --input $(SCIMAGO_INPUT)
endif

.PHONY: metrics-scimago-fetch metrics-update metrics-update-all metrics-check

metrics-scimago-fetch:
	./scripts/biblio/fetch_scimago_csv.sh $(SCIMAGO_ARGS)

metrics-update:
	$(PYTHON) scripts/biblio/metrics_update.py $(METRICS_ARGS)

metrics-update-all: metrics-scimago-fetch metrics-update

metrics-check:
	$(PYTHON) scripts/biblio/metrics_update.py --offline --dry-run $(METRICS_ARGS)
	bundle exec jekyll build
