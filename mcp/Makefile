# @gacontext-owner: provider
# @gacontext-origin: seeded-once; implement domain recipes here
# The caller's explicit MCP_CONSUMER_WORKSPACE remains inherited unchanged.

PYTHON ?= python3
.PHONY: build check smoke smoke-edition stdio
build:
	@$(PYTHON) scripts/shared_practice/prepare_images.py \
	  --output "$${SHARED_OUTPUT:?new preparation directory required}" \
	  --endpoint "$${SHARED_DOCKER_ENDPOINT:?explicit endpoint required}" \
	  --daemon-id "$${SHARED_DAEMON_ID:?exact daemon required}" \
	  --sdk-wheel "$${SHARED_SDK_WHEEL:?verified SDK wheel required}" \
	  --web-wheel "$${SHARED_WEB_WHEEL:?prepared owner wheel required}"
check:
	@$(PYTHON) -I -B -m gacontext_runtime scaffold check --repo "$(CURDIR)"
smoke:
	@$(PYTHON) test/shared_practice_smoke.py \
	  --output "$${SHARED_TEST_ROOT:?new isolated test root required}" \
	  --evidence-dir "$${SHARED_EVIDENCE_DIR:?durable evidence directory required}" \
	  --common-harness "$${SHARED_COMMON_HARNESS:?pinned common harness required}" \
	  --sdk-wheel "$${SHARED_SDK_WHEEL:?verified SDK wheel required}" \
	  --web-wheel "$${SHARED_WEB_WHEEL:?prepared owner wheel required}"
smoke-edition:
	@$(PYTHON) test/shared_edition_smoke.py \
	  --output "$${SHARED_TEST_ROOT:?new isolated test root required}" \
	  --evidence-dir "$${SHARED_EVIDENCE_DIR:?durable evidence directory required}" \
	  --common-harness "$${SHARED_COMMON_HARNESS:?pinned common harness required}" \
	  --sdk-wheel "$${SHARED_SDK_WHEEL:?verified SDK wheel required}" \
	  --web-wheel "$${SHARED_WEB_WHEEL:?prepared owner wheel required}" \
	  --qgis-bundle "$${SHARED_QGIS_BUNDLE:?verified native fixture directory required}" \
	  --verifier-archive "$${SHARED_VERIFIER_ARCHIVE:?prepared exact private image archive required}"
stdio:
	@test -n "$${UNALTRAWEB_SHARED_JOB_CONTEXT:-}" || { printf '%s\n' 'Select a prepared common task/job context first.' >&2; exit 2; }
	@exec $(PYTHON) -B -m unaltraweb_mcp.cli --project "$${MCP_CONSUMER_WORKSPACE:?explicit consumer required}" mcp serve
