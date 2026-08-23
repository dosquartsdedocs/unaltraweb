PYTHON ?= python3
PROJECT ?= .
TEMPLATE_PATH ?=
INIT_SITE_PROFILE ?= unaltreselfie
SITE_PROFILE ?=
SITE_TITLE ?=
BASEURL ?=
URL ?=
DEFAULT_LANG ?=
LANGUAGES ?=
METRICS_ARGS ?=
SCIMAGO_INPUT ?=
COMPUTE_PYTHON_IMAGE ?=
COMPUTE_R_IMAGE ?=
COMPUTE_SOURCE ?=
COMPUTE_CONFIRM_OVERWRITE ?= 0
COMPUTE_STALE_ONLY ?= 0
COMPUTE_MODE ?=
COMPUTE_SCRIPT := $(CURDIR)/scripts/computations/render.py
COMPUTE_PYTHON_LOCAL_IMAGE ?= unaltraweb-compute-python:local
COMPUTE_R_LOCAL_IMAGE ?= unaltraweb-compute-r:local
COMPUTE_DOCKER_BUILD_NETWORK ?= default
COMPUTE_CPUS ?= 4
COMPUTE_MEMORY ?= 8g
COMPUTE_PIDS_LIMIT ?= 512
RSTUDIO_PORT ?= 8787
WEB_CAPTURE_SOURCE ?=
WEB_CAPTURE_BASE_URL ?=
WEB_CAPTURE_DOCKER_NETWORK ?=
WEB_CAPTURE_SERVICE_HOST ?=
WEB_CAPTURE_CONFIRM_OVERWRITE ?= 0
WEB_CAPTURE_SCRIPT := $(CURDIR)/scripts/web_captures/render.py
WEB_CAPTURE_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-web-capture:main
WEB_CAPTURE_DOCKER_BUILD_NETWORK ?= default
VEGAVISUALS_PATH ?= $(abspath $(PROJECT)/../vegavisuals)
VEGAVISUALS_CLI ?=
DOCKER_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb:main
MANUAL_PDF_IMAGE ?= unaltraweb-manual-pdf:local
MANUAL_PDF_LANG ?=
MANUAL_PDF_PUBLISH_DRY_RUN ?= 1
DOCS_CONTAINER ?= unaltraweb-docs-local
DOCS_HOST ?= 0.0.0.0
DOCS_PORT ?= 4000
PUBLISH_REMOTE ?= origin
PUBLISH_BRANCH ?= gh-pages
PUBLISH_SOURCE ?= tmp/docs-site
PUBLISH_WORKTREE ?= tmp/publish-$(PUBLISH_BRANCH)
PUBLISH_DRY_RUN ?= 0
LOCAL_UID ?= $(shell id -u)
LOCAL_GID ?= $(shell id -g)
SCIMAGO_ARGS :=
ifneq ($(strip $(SCIMAGO_INPUT)),)
SCIMAGO_ARGS += --input $(SCIMAGO_INPUT)
endif

.PHONY: docs-build docs-serve docs-publish docs-down metrics-scimago-fetch metrics-update metrics-update-all metrics-check manual-pdf-image manual-pdf-status manual-pdf-check manual-pdf-build manual-pdf-publish manual-pdf-sync manual-compute-status manual-compute-check manual-compute-render manual-compute-render-figures manual-compute-image-python manual-compute-image-r manual-compute-images manual-compute-rstudio compute-base-image-python compute-base-image-r web-capture-status web-capture-check web-capture-render web-capture-image visualization-status visualization-check visualization-render
.PHONY: mcp-build mcp-init mcp-check mcp-smoke mcp-stdio mcp-list-tools mcp-starter-templates mcp-initialize-site mcp-site-context mcp-profile-check mcp-manual-source-quality-check mcp-manual-editorial-quality-check mcp-manual-authoring-capabilities mcp-manual-computation-status mcp-manual-computation-check mcp-manual-computation-render mcp-manual-computation-render-figures mcp-web-capture-status mcp-web-capture-check mcp-web-capture-render mcp-manual-pdf-status mcp-manual-pdf-build mcp-manual-pdf-publish mcp-profile-prune-plan mcp-profile-prune mcp-content-inventory mcp-language-policy mcp-content-approval-inventory mcp-translation-plan mcp-bibliography-inventory mcp-bibliometrics-check mcp-build-health

mcp-build: ## Validate the lightweight Python MCP control plane
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m compileall -q src/unaltraweb_mcp

mcp-init: mcp-build ## Initialize reusable MCP dependencies without starting services

mcp-check: ## Verify the source checkout can serve the MCP CLI contract
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli version

mcp-smoke: mcp-check ## Run a fast deterministic MCP smoke check against PROJECT
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp starter-templates >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp site-context >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp profile-check >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-source-quality-check >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-editorial-quality-check >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-authoring-capabilities >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-computation-status >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp web-capture-status >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp translation-plan >/dev/null
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp bibliography-inventory >/dev/null

mcp-stdio: ## Serve the unaltraweb MCP through the standard stdio launcher
	PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp serve

mcp-list-tools: ## List MCP resources, prompts, and tools exposed by this factory
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp list-tools

mcp-starter-templates: ## List starter website templates available to initialize PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp starter-templates

mcp-initialize-site: ## Initialize PROJECT from the starter template without overwriting existing files
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp initialize-site --template-path "$(TEMPLATE_PATH)" --site-profile "$(INIT_SITE_PROFILE)" --title "$(SITE_TITLE)" --baseurl "$(BASEURL)" --url "$(URL)" --default-lang "$(DEFAULT_LANG)" --languages "$(LANGUAGES)"

mcp-site-context: ## Print JSON site context for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp site-context

mcp-profile-check: ## Print JSON profile contract checks for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp profile-check

mcp-manual-source-quality-check: ## Print JSON manual source hygiene checks for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-source-quality-check

mcp-manual-editorial-quality-check: ## Print JSON publishable-prose checks for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-editorial-quality-check

mcp-manual-authoring-capabilities: ## Print supported manual component syntax and compatibility
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-authoring-capabilities

mcp-manual-computation-status: ## Inspect executable manual sources and generated artefacts
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-computation-status --source "$(COMPUTE_SOURCE)"

mcp-manual-computation-check: ## Fail when executable manual results are stale
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-computation-check --source "$(COMPUTE_SOURCE)"

mcp-manual-computation-render: ## Execute and publish versioned manual computation outputs
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-computation-render --source "$(COMPUTE_SOURCE)" $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_CONFIRM_OVERWRITE)),--confirm-overwrite,) $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_STALE_ONLY)),--stale-only,)

mcp-manual-computation-render-figures: ## Render all stale figure-only computation outputs without touching fresh or unmanaged files
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-computation-render-figures

mcp-web-capture-status: ## Inspect web capture recipes and generated artefacts
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp web-capture-status --source "$(WEB_CAPTURE_SOURCE)"

mcp-web-capture-check: ## Fail when web capture artefacts are stale
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp web-capture-check --source "$(WEB_CAPTURE_SOURCE)"

mcp-web-capture-render: ## Start an isolated preview and publish annotated SVG artefacts
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp web-capture-render --source "$(WEB_CAPTURE_SOURCE)" $(if $(filter 1 true TRUE yes YES y Y,$(WEB_CAPTURE_CONFIRM_OVERWRITE)),--confirm-overwrite,)

mcp-manual-pdf-status: ## Inspect manual PDF state for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-pdf-status --language "$(MANUAL_PDF_LANG)"

mcp-manual-pdf-build: ## Build the manual PDF for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-pdf-build --language "$(MANUAL_PDF_LANG)"

mcp-manual-pdf-publish: ## Dry-run manual PDF publication for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp manual-pdf-publish --language "$(MANUAL_PDF_LANG)"

mcp-profile-prune-plan: ## Print JSON dry-run prune candidates for the active or selected profile
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp profile-prune-plan --site-profile "$(SITE_PROFILE)"

mcp-profile-prune: ## Dry-run profile prune; use the MCP tool with confirm_prune for destructive runs
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp profile-prune --site-profile "$(SITE_PROFILE)"

mcp-content-inventory: ## Print JSON content inventory for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp content-inventory

mcp-language-policy: ## Print JSON default language and translation workflow settings for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp language-policy

mcp-content-approval-inventory: ## Print JSON editorial approval state for PROJECT content
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp content-approval-inventory

mcp-translation-plan: ## Print JSON missing translations for approved default-language content
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp translation-plan

mcp-bibliography-inventory: ## Print JSON bibliography inventory for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp bibliography-inventory

mcp-bibliometrics-check: ## Run the offline bibliometrics check for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp bibliometrics-check

mcp-build-health: ## Inspect existing _site build artefacts for PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp build-health

manual-compute-status: ## Inspect executable manual sources and generated artefacts
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" status --project "$(abspath $(PROJECT))" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)

manual-compute-check: ## Fail when executable manual results are stale
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" check --project "$(abspath $(PROJECT))" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)

manual-compute-render: ## Execute sources and atomically publish Markdown and figures
	@set -e; \
	results=$$(mktemp); trap 'rm -f "$$results"' EXIT; \
	status=$$(COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" status --project "$(abspath $(PROJECT))" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)); \
	engines=$$(printf '%s' "$$status" | $(PYTHON) -c 'import json,sys; data=json.load(sys.stdin); print(" ".join(f"{engine}={image}" for engine,image in sorted({(item["engine"], item["image"]["image"]) for item in data["sources"]})))'); \
	for selection in $$engines; do \
	  engine=$${selection%%=*}; image=$${selection#*=}; \
	  python_image="$(COMPUTE_PYTHON_IMAGE)"; r_image="$(COMPUTE_R_IMAGE)"; \
	  if test "$$engine" = "r"; then r_image="$$image"; else python_image="$$image"; fi; \
	  if ! docker image inspect "$$image" >/dev/null 2>&1; then \
	    COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(abspath $(PROJECT))" --engine "$$engine" >/dev/null; \
	  fi; \
	  identity=$$(docker image inspect "$$image" --format '{{.Id}}'); \
	  digest=$$(docker image inspect "$$image" --format '{{join .RepoDigests ","}}'); \
	  docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit "$(COMPUTE_PIDS_LIMIT)" --cpus "$(COMPUTE_CPUS)" --memory "$(COMPUTE_MEMORY)" --tmpfs /tmp:rw,noexec,nosuid,size=1g \
	    -e HOME=/tmp -e COMPUTE_PYTHON_IMAGE="$$python_image" -e COMPUTE_R_IMAGE="$$r_image" \
	    -e UNALTRAWEB_COMPUTE_IMAGE_ID="$$identity" -e UNALTRAWEB_COMPUTE_IMAGE_DIGEST="$$digest" \
	    -v "$(abspath $(PROJECT)):/project:rw" -v "$(COMPUTE_SCRIPT):/opt/unaltraweb/computations/render.py:ro" -w /project --entrypoint python3 "$$image" \
	    /opt/unaltraweb/computations/render.py render --project /project --engine "$$engine" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_CONFIRM_OVERWRITE)),--confirm-overwrite,) $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_STALE_ONLY)),--stale-only,) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",) >> "$$results"; \
	done; \
	if test -z "$(strip $(COMPUTE_SOURCE))"; then $(PYTHON) "$(COMPUTE_SCRIPT)" prune --project "$(abspath $(PROJECT))" >/dev/null; fi; \
	$(PYTHON) -c 'import json,sys; text=open(sys.argv[1], encoding="utf-8").read(); decoder=json.JSONDecoder(); items=[]; index=0; exec("while index < len(text):\n index += len(text[index:]) - len(text[index:].lstrip())\n if index >= len(text): break\n item,index = decoder.raw_decode(text,index)\n items.append(item)"); rendered=[entry for item in items for entry in item.get("rendered", [])]; print(json.dumps({"project":"$(abspath $(PROJECT))","rendered":rendered,"rendered_count":len(rendered),"ok":all(item.get("ok",False) for item in items)}, indent=2))' "$$results"

manual-compute-render-figures: override COMPUTE_STALE_ONLY := 1
manual-compute-render-figures: override COMPUTE_MODE := figure
manual-compute-render-figures: manual-compute-render ## Render only stale figure-mode computation sources

manual-compute-image-python: ## Build or pull the selected Python computation image
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(abspath $(PROJECT))" --engine python

manual-compute-image-r: ## Build or pull the selected R computation image
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(abspath $(PROJECT))" --engine r

manual-compute-images: manual-compute-image-python manual-compute-image-r

compute-base-image-python: ## Build the reusable local Python computation image
	docker build --network "$(COMPUTE_DOCKER_BUILD_NETWORK)" -f scripts/computations/python/Dockerfile -t "$(COMPUTE_PYTHON_LOCAL_IMAGE)" .

compute-base-image-r: ## Build the reusable local R computation image
	docker build --network "$(COMPUTE_DOCKER_BUILD_NETWORK)" -f scripts/computations/r/Dockerfile -t "$(COMPUTE_R_LOCAL_IMAGE)" .

manual-compute-rstudio: manual-compute-image-r ## Open the selected R computation image in RStudio Server
	@image=$$(COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" resolve --project "$(abspath $(PROJECT))" --engine r | $(PYTHON) -c 'import json,sys; print(json.load(sys.stdin)["image"])'); \
	docker run --rm -it -p "127.0.0.1:$(RSTUDIO_PORT):8787" -e DISABLE_AUTH=true -e USERID="$(LOCAL_UID)" -e GROUPID="$(LOCAL_GID)" -v "$(abspath $(PROJECT)):/home/rstudio/project" -w /home/rstudio/project "$$image" /init

web-capture-status: ## Inspect web capture recipes and generated artefacts
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" status --project "$(abspath $(PROJECT))" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",)

web-capture-check: ## Fail when web capture PNG, SVG, or edited overrides are stale
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" check --project "$(abspath $(PROJECT))" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",)

web-capture-render: ## Capture a trusted running preview and publish PNG plus annotated SVG
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" WEB_CAPTURE_DOCKER_BUILD_NETWORK="$(WEB_CAPTURE_DOCKER_BUILD_NETWORK)" WEB_CAPTURE_DOCKER_NETWORK="$(WEB_CAPTURE_DOCKER_NETWORK)" WEB_CAPTURE_SERVICE_HOST="$(WEB_CAPTURE_SERVICE_HOST)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" render --project "$(abspath $(PROJECT))" --base-url "$(WEB_CAPTURE_BASE_URL)" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",) $(if $(filter 1 true TRUE yes YES y Y,$(WEB_CAPTURE_CONFIRM_OVERWRITE)),--confirm-overwrite,)

web-capture-image: ## Build the isolated Playwright web capture image
	docker build --network "$(WEB_CAPTURE_DOCKER_BUILD_NETWORK)" -f scripts/web_captures/Dockerfile -t "$(WEB_CAPTURE_IMAGE)" .

define run_vegavisuals
	@if test ! -f "$(abspath $(PROJECT))/.vegavisuals.yml"; then \
	  printf '%s\n' 'No .vegavisuals.yml; skipping visualization $(1).'; \
	elif test -n "$(strip $(VEGAVISUALS_CLI))"; then \
	  "$(VEGAVISUALS_CLI)" --project "$(abspath $(PROJECT))" $(1); \
	elif test -f "$(abspath $(VEGAVISUALS_PATH))/src/vegavisuals/cli.py"; then \
	  PYTHONPATH="$(abspath $(VEGAVISUALS_PATH))/src$${PYTHONPATH:+:$$PYTHONPATH}" $(PYTHON) -m vegavisuals.cli --project "$(abspath $(PROJECT))" $(1); \
	elif command -v vegavisuals >/dev/null 2>&1; then \
	  vegavisuals --project "$(abspath $(PROJECT))" $(1); \
	else \
	  printf '%s\n' 'vegavisuals CLI not found. Set VEGAVISUALS_CLI or VEGAVISUALS_PATH, or install vegavisuals.' >&2; \
	  exit 1; \
	fi
endef

visualization-status: ## Report Vega visualization manifest and output freshness when configured
	$(call run_vegavisuals,status)

visualization-check: ## Reject stale Vega visualization outputs when configured
	$(call run_vegavisuals,check)

visualization-render: ## Render missing or stale Vega visualizations when configured
	$(call run_vegavisuals,render-all)

manual-pdf-image: ## Build the isolated local Pandoc/XeLaTeX image
	docker build -f scripts/manual/Dockerfile -t "$(MANUAL_PDF_IMAGE)" scripts/manual

manual-pdf-status: manual-compute-check web-capture-check visualization-check manual-pdf-image ## Inspect manual PDF configuration and artefacts
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" status --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

manual-pdf-check: manual-compute-check web-capture-check visualization-check manual-pdf-image ## Reject stale or unpublished manual PDF artefacts
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" check --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

manual-pdf-build: manual-compute-check web-capture-check visualization-check manual-pdf-image ## Build manual PDFs and cover previews under tmp
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" build --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

manual-pdf-publish: manual-compute-check web-capture-check visualization-check manual-pdf-image ## Copy built PDF artefacts to configured public paths
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" publish --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",) $(if $(filter 1 true TRUE yes YES y Y,$(MANUAL_PDF_PUBLISH_DRY_RUN)),--dry-run,)

manual-pdf-sync: manual-compute-check web-capture-check visualization-check manual-pdf-image ## Build and copy changed manual PDFs to their public paths
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" sync --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

docs-build: visualization-check
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -e BUNDLE_GEMFILE=docs/Gemfile -e BUNDLE_APP_CONFIG=/work/tmp/docs_bundle_config -e BUNDLE_PATH=/work/tmp/docs_bundle_path -v "$(CURDIR):/work" -w /work $(DOCKER_IMAGE) bash -lc 'git config --global --add safe.directory /work >/dev/null 2>&1 || true; mkdir -p tmp/docs_bundle_config tmp/docs_bundle_path; bundle check || bundle install; core_config=$$(bundle exec ruby -e "spec = Gem::Specification.find_by_name(\"unaltraweb\"); print File.join(spec.full_gem_path, \"_config.yml\")"); bundle exec jekyll build --source docs --destination tmp/docs-site --config "$$core_config,docs/_config.yml" --disable-disk-cache'

docs-serve: visualization-check
	-docker rm -f "$(DOCS_CONTAINER)" >/dev/null 2>&1 || true
	docker run --name "$(DOCS_CONTAINER)" --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -e BUNDLE_GEMFILE=docs/Gemfile -e BUNDLE_APP_CONFIG=/work/tmp/docs_bundle_config -e BUNDLE_PATH=/work/tmp/docs_bundle_path -p "$(DOCS_PORT):$(DOCS_PORT)" -v "$(CURDIR):/work" -w /work $(DOCKER_IMAGE) bash -lc 'git config --global --add safe.directory /work >/dev/null 2>&1 || true; mkdir -p tmp/docs_bundle_config tmp/docs_bundle_path; bundle check || bundle install; core_config=$$(bundle exec ruby -e "spec = Gem::Specification.find_by_name(\"unaltraweb\"); print File.join(spec.full_gem_path, \"_config.yml\")"); bundle exec jekyll serve --source docs --destination tmp/docs-site --config "$$core_config,docs/_config.yml" --host $(DOCS_HOST) --port $(DOCS_PORT) --disable-disk-cache'

docs-publish: docs-build
	PUBLISH_REMOTE="$(PUBLISH_REMOTE)" PUBLISH_BRANCH="$(PUBLISH_BRANCH)" PUBLISH_SOURCE="$(PUBLISH_SOURCE)" PUBLISH_WORKTREE="$(PUBLISH_WORKTREE)" PUBLISH_DRY_RUN="$(PUBLISH_DRY_RUN)" scripts/deploy/publish_branch.sh

docs-down:
	-docker rm -f "$(DOCS_CONTAINER)" >/dev/null 2>&1 || true

metrics-scimago-fetch:
	./scripts/biblio/fetch_scimago_csv.sh $(SCIMAGO_ARGS)

metrics-update:
	$(PYTHON) scripts/biblio/metrics_update.py $(METRICS_ARGS)

metrics-update-all: metrics-scimago-fetch metrics-update

metrics-check:
	$(PYTHON) scripts/biblio/metrics_update.py --offline --dry-run $(METRICS_ARGS)
	bundle exec jekyll build
