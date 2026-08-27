PYTHON ?= python3
PROJECT ?= .
PROJECT_ROOT := $(shell realpath -m -- "$(PROJECT)")
MCP_RUNTIME_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb:0.3.0
MCP_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0
MCP_DOCKER_BUILD_NETWORK ?= default
INIT_SITE_PROFILE ?= unaltreselfie
NEW_WEB_PROFILE ?= unaltreselfie
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
COMPUTE_PYTHON_LOCAL_IMAGE ?= unaltraweb-compute-python:dev
COMPUTE_R_LOCAL_IMAGE ?= unaltraweb-compute-r:dev
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
WEB_CAPTURE_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-web-capture:0.3.0
WEB_CAPTURE_DEV_IMAGE ?= unaltraweb-web-capture:dev
WEB_CAPTURE_DOCKER_BUILD_NETWORK ?= default
VEGAVISUALS_PATH ?= $(PROJECT_ROOT)/../vegavisuals
VEGAVISUALS_ROOT := $(shell realpath -m -- "$(VEGAVISUALS_PATH)")
VEGAVISUALS_CLI ?=
DOCKER_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb:0.3.0
MANUAL_PDF_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-manual-pdf:0.3.0
MANUAL_PDF_DEV_IMAGE ?= unaltraweb-manual-pdf:dev
MANUAL_PDF_LANG ?=
MANUAL_PDF_PUBLISH_DRY_RUN ?= 1
UNALTRAWEB_WORKER_ROLE ?=
UNALTRAWEB_WORKER_PROJECT ?=
UNALTRAWEB_WORKER_TOKEN ?=
WORKER_LABEL_ARGS = $(if $(strip $(UNALTRAWEB_WORKER_TOKEN)),--label "io.context.mcp-factory=unaltraweb" --label "io.context.mcp-role=$(UNALTRAWEB_WORKER_ROLE)" --label "io.context.mcp-project=$(UNALTRAWEB_WORKER_PROJECT)" --label "io.context.mcp-worker-token=$(UNALTRAWEB_WORKER_TOKEN)",)
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
SCIMAGO_ARGS += --input "$(SCIMAGO_INPUT)"
endif

.PHONY: distribution-check distribution-release-check distribution-doctor workflow-check wheel-check gem-check docs-build docs-serve docs-publish docs-down metrics-scimago-fetch metrics-update metrics-update-all metrics-check manual-pdf-image manual-pdf-image-dev manual-pdf-preflight manual-pdf-status manual-pdf-check manual-pdf-build manual-pdf-publish manual-pdf-sync manual-compute-status manual-compute-check manual-compute-render manual-compute-render-figures manual-compute-image-python manual-compute-image-r manual-compute-images manual-compute-rstudio compute-base-image-python compute-base-image-r web-capture-status web-capture-check web-capture-render web-capture-image visualization-status visualization-check visualization-render
.PHONY: mcp-runtime-image mcp-image mcp-build mcp-check mcp-smoke mcp-smoke-prebuilt mcp-stdio mcp-down mcp-down-all mcp-list-tools mcp-starter-templates mcp-new-web mcp-initialize-site mcp-site-context mcp-profile-check mcp-manual-source-quality-check mcp-manual-editorial-quality-check mcp-manual-authoring-capabilities mcp-manual-computation-status mcp-manual-computation-check mcp-manual-computation-render mcp-manual-computation-render-figures mcp-web-capture-status mcp-web-capture-check mcp-web-capture-render mcp-manual-pdf-status mcp-manual-pdf-build mcp-manual-pdf-publish mcp-profile-prune-plan mcp-profile-prune mcp-content-inventory mcp-language-policy mcp-content-approval-inventory mcp-translation-plan mcp-bibliography-inventory mcp-bibliometrics-check mcp-build-health

distribution-check: ## Validate component/version parity, release selections, and the wheel boundary
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) scripts/validate_distribution.py

distribution-release-check: ## Require every selected component release to be published
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) scripts/validate_distribution.py --require-release-ready

distribution-doctor: ## Inspect the selected distribution and PROJECT without network access
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli doctor --project "$(PROJECT)"

workflow-check: ## Validate GitHub Actions syntax and publication safety gates
	@$(PYTHON) scripts/validate_workflows.py

wheel-check: ## Build and exercise a clean factory-free wheel install
	@$(PYTHON) scripts/test_wheel_install.py

gem-check: ## Build the gem and verify its package-owned contract files
	@$(PYTHON) scripts/test_gem_build.py

mcp-runtime-image: ## Build the reusable Jekyll runtime used by the MCP
	docker build --network "$(MCP_DOCKER_BUILD_NETWORK)" -t "$(MCP_RUNTIME_IMAGE)" .

mcp-image: mcp-runtime-image ## Build the Dockerized FastMCP control plane
	docker build --network "$(MCP_DOCKER_BUILD_NETWORK)" --build-arg "UNALTRAWEB_RUNTIME_IMAGE=$(MCP_RUNTIME_IMAGE)" -t "$(MCP_IMAGE)" -f Dockerfile.mcp .

mcp-build: mcp-image ## Prepare the Docker images used by MCP sessions, builds, and previews

mcp-check: mcp-image ## Verify the Dockerized MCP CLI contract
	docker run --rm --entrypoint unaltraweb-mcp "$(MCP_IMAGE)" version

mcp-smoke: mcp-build ## Build and prove a real MCP stdio connection
	@$(MAKE) --silent --no-print-directory mcp-smoke-prebuilt MCP_IMAGE="$(MCP_IMAGE)"

mcp-smoke-prebuilt: ## Prove a real MCP stdio connection using the selected prebuilt MCP image
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp --entrypoint python3 "$(MCP_IMAGE)" /opt/unaltraweb/test/mcp_smoke.py
	@mkdir -p "$(CURDIR)/tmp/mcp-preview-smoke"
	@docker_socket="$${UNALTRAWEB_DOCKER_SOCKET:-/var/run/docker.sock}"; socket_group=$$(stat -c '%g' "$$docker_socket"); \
	image_id=$$(docker image inspect --format '{{.Id}}' "$(MCP_IMAGE)"); \
	preview_port=$$(docker run --rm --network host --entrypoint python3 "$$image_id" -c 'import socket; listener=socket.socket(); listener.bind(("127.0.0.1", 0)); print(listener.getsockname()[1]); listener.close()'); \
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" --group-add "$$socket_group" \
	  -e HOME=/tmp -e "UNALTRAWEB_DOCKER_ROOT=$(CURDIR)/tmp/mcp-preview-smoke" \
	  -e "UNALTRAWEB_PROJECT_USER=$(LOCAL_UID):$(LOCAL_GID)" -e "UNALTRAWEB_MCP_IMAGE=$$image_id" \
	  -e "UNALTRAWEB_PREVIEW_PORT=$$preview_port" \
	  -v "$$docker_socket:/var/run/docker.sock" -v "$(CURDIR)/tmp/mcp-preview-smoke:/workspace" -w /workspace \
	  --entrypoint python3 "$$image_id" /opt/unaltraweb/test/mcp_preview_smoke.py

mcp-stdio: ## Serve the current PROJECT through the Dockerized stdio MCP
	@exec "$(CURDIR)/scripts/unaltraweb-mcp-bootstrap.sh" --image "$(MCP_IMAGE)"

mcp-down: ## Remove MCP resources owned by PROJECT
	@project_id="$$(/bin/sh "$(CURDIR)/scripts/unaltraweb-mcp-project-id.sh" "$(PROJECT_ROOT)")" || exit $$?; \
	containers="$$(docker ps -aq --filter "label=io.context.mcp-factory=unaltraweb" --filter "label=io.context.mcp-project=$$project_id")" || exit $$?; \
	if [ -n "$$containers" ]; then docker rm -f $$containers || exit $$?; fi; \
	networks="$$(docker network ls -q --filter "label=io.context.mcp-factory=unaltraweb" --filter "label=io.context.mcp-project=$$project_id")" || exit $$?; \
	if [ -n "$$networks" ]; then docker network rm $$networks; fi

mcp-down-all: ## Remove all MCP resources owned by this factory (maintainers only)
	@containers="$$(docker ps -aq --filter "label=io.context.mcp-factory=unaltraweb")" || exit $$?; \
	if [ -n "$$containers" ]; then docker rm -f $$containers || exit $$?; fi; \
	networks="$$(docker network ls -q --filter "label=io.context.mcp-factory=unaltraweb")" || exit $$?; \
	if [ -n "$$networks" ]; then docker network rm $$networks; fi

mcp-list-tools: ## List MCP resources, prompts, and tools exposed by this factory
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp list-tools

mcp-starter-templates: ## List starter website templates available to initialize PROJECT
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp starter-templates

mcp-new-web: ## Create PROJECT from the package-owned scaffold for NEW_WEB_PROFILE
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" new-web --site-profile "$(NEW_WEB_PROFILE)" --title "$(SITE_TITLE)" --baseurl "$(BASEURL)" --url "$(URL)" --default-lang "$(DEFAULT_LANG)" --languages "$(LANGUAGES)"

mcp-initialize-site: ## Compatibility alias for package-owned website creation
	@PYTHONPATH="$(CURDIR)/src" $(PYTHON) -m unaltraweb_mcp.cli --project "$(PROJECT)" mcp initialize-site --site-profile "$(INIT_SITE_PROFILE)" --title "$(SITE_TITLE)" --baseurl "$(BASEURL)" --url "$(URL)" --default-lang "$(DEFAULT_LANG)" --languages "$(LANGUAGES)"

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
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" status --project "$(PROJECT_ROOT)" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)

manual-compute-check: ## Fail when executable manual results are stale
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" check --project "$(PROJECT_ROOT)" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)

manual-compute-render: ## Execute sources and atomically publish Markdown and figures
	@set -e; \
	runtime_dir="$(PROJECT_ROOT)/tmp/.unaltraweb/computations"; \
	mkdir -p "$$runtime_dir"; runtime_script=$$(mktemp "$$runtime_dir/render.XXXXXX"); cp "$(COMPUTE_SCRIPT)" "$$runtime_script"; \
	results=$$(mktemp); cidfiles=""; trap 'rm -f "$$results" "$$runtime_script" $$cidfiles' EXIT; \
	status=$$(COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" status --project "$(PROJECT_ROOT)" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",)); \
	engines=$$(printf '%s' "$$status" | $(PYTHON) -c 'import json,sys; data=json.load(sys.stdin); print(" ".join(f"{engine}={image}" for engine,image in sorted({(item["engine"], item["image"]["image"]) for item in data["sources"]})))'); \
	for selection in $$engines; do \
	  engine=$${selection%%=*}; image=$${selection#*=}; \
	  python_image="$(COMPUTE_PYTHON_IMAGE)"; r_image="$(COMPUTE_R_IMAGE)"; \
	  if test "$$engine" = "r"; then r_image="$$image"; else python_image="$$image"; fi; \
	  if ! docker image inspect "$$image" >/dev/null 2>&1; then \
	    COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(PROJECT_ROOT)" --engine "$$engine" >/dev/null; \
	  fi; \
	  identity=$$(docker image inspect "$$image" --format '{{.Id}}'); \
	  digest=$$(docker image inspect "$$image" --format '{{join .RepoDigests ","}}'); \
	  set --; if test -n "$(UNALTRAWEB_WORKER_TOKEN)"; then cidfile="$$runtime_dir/worker-$(UNALTRAWEB_WORKER_TOKEN)-$$engine.cid"; rm -f "$$cidfile"; cidfiles="$$cidfiles $$cidfile"; set -- --cidfile "$$cidfile"; fi; \
	  docker run --rm "$$@" $(WORKER_LABEL_ARGS) --user "$(LOCAL_UID):$(LOCAL_GID)" --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit "$(COMPUTE_PIDS_LIMIT)" --cpus "$(COMPUTE_CPUS)" --memory "$(COMPUTE_MEMORY)" --tmpfs /tmp:rw,noexec,nosuid,size=1g \
	    -e HOME=/tmp -e COMPUTE_PYTHON_IMAGE="$$python_image" -e COMPUTE_R_IMAGE="$$r_image" \
	    -e UNALTRAWEB_COMPUTE_IMAGE_ID="$$identity" -e UNALTRAWEB_COMPUTE_IMAGE_DIGEST="$$digest" \
	    -v "$(PROJECT_ROOT):/project:rw" -v "$$runtime_script:/opt/unaltraweb/computations/render.py:ro" -w /project --entrypoint python3 "$$image" \
	    /opt/unaltraweb/computations/render.py render --project /project --engine "$$engine" $(if $(strip $(COMPUTE_SOURCE)),--source "$(COMPUTE_SOURCE)",) $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_CONFIRM_OVERWRITE)),--confirm-overwrite,) $(if $(filter 1 true TRUE yes YES y Y,$(COMPUTE_STALE_ONLY)),--stale-only,) $(if $(strip $(COMPUTE_MODE)),--mode "$(COMPUTE_MODE)",) >> "$$results"; \
	done; \
	if test -z "$(strip $(COMPUTE_SOURCE))"; then $(PYTHON) "$(COMPUTE_SCRIPT)" prune --project "$(PROJECT_ROOT)" >/dev/null; fi; \
	$(PYTHON) -c 'import json,sys; text=open(sys.argv[1], encoding="utf-8").read(); decoder=json.JSONDecoder(); items=[]; index=0; exec("while index < len(text):\n index += len(text[index:]) - len(text[index:].lstrip())\n if index >= len(text): break\n item,index = decoder.raw_decode(text,index)\n items.append(item)"); rendered=[entry for item in items for entry in item.get("rendered", [])]; print(json.dumps({"project":"$(PROJECT_ROOT)","rendered":rendered,"rendered_count":len(rendered),"ok":all(item.get("ok",False) for item in items)}, indent=2))' "$$results"

manual-compute-render-figures: override COMPUTE_STALE_ONLY := 1
manual-compute-render-figures: override COMPUTE_MODE := figure
manual-compute-render-figures: manual-compute-render ## Render only stale figure-mode computation sources

manual-compute-image-python: ## Build or pull the selected Python computation image
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(PROJECT_ROOT)" --engine python

manual-compute-image-r: ## Build or pull the selected R computation image
	@COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" COMPUTE_DOCKER_BUILD_NETWORK="$(COMPUTE_DOCKER_BUILD_NETWORK)" $(PYTHON) "$(COMPUTE_SCRIPT)" image --project "$(PROJECT_ROOT)" --engine r

manual-compute-images: manual-compute-image-python manual-compute-image-r

compute-base-image-python: ## Build the reusable local Python computation image
	docker build --network "$(COMPUTE_DOCKER_BUILD_NETWORK)" -f scripts/computations/python/Dockerfile -t "$(COMPUTE_PYTHON_LOCAL_IMAGE)" .

compute-base-image-r: ## Build the reusable local R computation image
	docker build --network "$(COMPUTE_DOCKER_BUILD_NETWORK)" -f scripts/computations/r/Dockerfile -t "$(COMPUTE_R_LOCAL_IMAGE)" .

manual-compute-rstudio: manual-compute-image-r ## Open the selected R computation image in RStudio Server
	@image=$$(COMPUTE_PYTHON_IMAGE="$(COMPUTE_PYTHON_IMAGE)" COMPUTE_R_IMAGE="$(COMPUTE_R_IMAGE)" $(PYTHON) "$(COMPUTE_SCRIPT)" resolve --project "$(PROJECT_ROOT)" --engine r | $(PYTHON) -c 'import json,sys; print(json.load(sys.stdin)["image"])'); \
	docker run --rm -it -p "127.0.0.1:$(RSTUDIO_PORT):8787" -e DISABLE_AUTH=true -e USERID="$(LOCAL_UID)" -e GROUPID="$(LOCAL_GID)" -v "$(PROJECT_ROOT):/home/rstudio/project" -w /home/rstudio/project "$$image" /init

web-capture-status: ## Inspect web capture recipes and generated artefacts
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" status --project "$(PROJECT_ROOT)" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",)

web-capture-check: ## Fail when web capture PNG, SVG, or edited overrides are stale
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" check --project "$(PROJECT_ROOT)" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",)

web-capture-render: ## Capture a trusted running preview and publish PNG plus annotated SVG
	@WEB_CAPTURE_IMAGE="$(WEB_CAPTURE_IMAGE)" WEB_CAPTURE_DOCKER_BUILD_NETWORK="$(WEB_CAPTURE_DOCKER_BUILD_NETWORK)" WEB_CAPTURE_DOCKER_NETWORK="$(WEB_CAPTURE_DOCKER_NETWORK)" WEB_CAPTURE_SERVICE_HOST="$(WEB_CAPTURE_SERVICE_HOST)" $(PYTHON) "$(WEB_CAPTURE_SCRIPT)" render --project "$(PROJECT_ROOT)" --base-url "$(WEB_CAPTURE_BASE_URL)" $(if $(strip $(WEB_CAPTURE_SOURCE)),--source "$(WEB_CAPTURE_SOURCE)",) $(if $(filter 1 true TRUE yes YES y Y,$(WEB_CAPTURE_CONFIRM_OVERWRITE)),--confirm-overwrite,)

web-capture-image: ## Build the isolated Playwright web capture image
	docker build --network "$(WEB_CAPTURE_DOCKER_BUILD_NETWORK)" -f scripts/web_captures/Dockerfile -t "$(WEB_CAPTURE_DEV_IMAGE)" .

define run_vegavisuals
	@if test ! -f "$(PROJECT_ROOT)/.vegavisuals.yml"; then \
	  printf '%s\n' 'No .vegavisuals.yml; skipping visualization $(1).'; \
	elif test -n "$(strip $(VEGAVISUALS_CLI))"; then \
	  "$(VEGAVISUALS_CLI)" --project "$(PROJECT_ROOT)" $(1); \
	elif test -f "$(VEGAVISUALS_ROOT)/src/vegavisuals/cli.py"; then \
	  PYTHONPATH="$(VEGAVISUALS_ROOT)/src$${PYTHONPATH:+:$$PYTHONPATH}" $(PYTHON) -m vegavisuals.cli --project "$(PROJECT_ROOT)" $(1); \
	elif command -v vegavisuals >/dev/null 2>&1; then \
	  vegavisuals --project "$(PROJECT_ROOT)" $(1); \
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

manual-pdf-image: ## Ensure the selected versioned Pandoc/XeLaTeX image is present
	@docker image inspect "$(MANUAL_PDF_IMAGE)" >/dev/null 2>&1 || docker pull "$(MANUAL_PDF_IMAGE)"

manual-pdf-image-dev: ## Build the explicitly named maintainer PDF development image
	docker build -f scripts/manual/Dockerfile -t "$(MANUAL_PDF_DEV_IMAGE)" scripts/manual

define run_manual_pdf_worker
	@set -e; runtime_dir="$(PROJECT_ROOT)/tmp/.unaltraweb/manual-pdf"; mkdir -p "$$runtime_dir"; set --; cidfile=""; \
	if test -n "$(UNALTRAWEB_WORKER_TOKEN)"; then cidfile="$$runtime_dir/worker-$(UNALTRAWEB_WORKER_TOKEN).cid"; rm -f "$$cidfile"; set -- --cidfile "$$cidfile"; fi; \
	trap 'test -z "$$cidfile" || rm -f "$$cidfile"' EXIT; \
	docker run --rm "$$@" $(WORKER_LABEL_ARGS) --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(PROJECT_ROOT):/project" -w /project "$(MANUAL_PDF_IMAGE)" $(1) --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",) $(2)
endef

manual-pdf-preflight: ## Run required PDF gates without contaminating the worker JSON stream
	@$(MAKE) --silent --no-print-directory manual-compute-check PROJECT="$(PROJECT_ROOT)" >/dev/null
	@$(MAKE) --silent --no-print-directory web-capture-check PROJECT="$(PROJECT_ROOT)" >/dev/null
	@docker image inspect "$(MANUAL_PDF_IMAGE)" >/dev/null 2>&1 || docker pull "$(MANUAL_PDF_IMAGE)" >/dev/null

manual-pdf-status: manual-pdf-preflight ## Inspect manual PDF configuration and artefacts
	$(call run_manual_pdf_worker,status)

manual-pdf-check: manual-pdf-preflight ## Reject stale or unpublished manual PDF artefacts
	$(call run_manual_pdf_worker,check)

manual-pdf-build: manual-pdf-preflight ## Build manual PDFs and cover previews under tmp
	$(call run_manual_pdf_worker,build)

manual-pdf-publish: manual-pdf-preflight ## Copy built PDF artefacts to configured public paths
	$(call run_manual_pdf_worker,publish,$(if $(filter 1 true TRUE yes YES y Y,$(MANUAL_PDF_PUBLISH_DRY_RUN)),--dry-run,))

manual-pdf-sync: manual-pdf-preflight ## Build and copy changed manual PDFs to their public paths
	$(call run_manual_pdf_worker,sync)

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
	@cd "$(PROJECT_ROOT)" && "$(CURDIR)/scripts/biblio/fetch_scimago_csv.sh" $(SCIMAGO_ARGS) 1>&2 && $(PYTHON) -c 'import json; print(json.dumps({"ok": True, "project": "$(PROJECT_ROOT)", "scimago": ".cache/scimago/scimagojr.csv"}, indent=2))'

metrics-update:
	@cd "$(PROJECT_ROOT)" && $(PYTHON) "$(CURDIR)/scripts/biblio/metrics_update.py" $(METRICS_ARGS) 1>&2 && $(PYTHON) -c 'import json; print(json.dumps({"ok": True, "project": "$(PROJECT_ROOT)", "updated": True}, indent=2))'

metrics-update-all:
	@$(MAKE) --silent --no-print-directory metrics-scimago-fetch PROJECT="$(PROJECT_ROOT)" SCIMAGO_INPUT="$(SCIMAGO_INPUT)" 1>&2
	@$(MAKE) --silent --no-print-directory metrics-update PROJECT="$(PROJECT_ROOT)" METRICS_ARGS="$(METRICS_ARGS)"

metrics-check:
	@cd "$(PROJECT_ROOT)" && $(PYTHON) "$(CURDIR)/scripts/biblio/metrics_update.py" --offline --dry-run $(METRICS_ARGS) 1>&2 && $(PYTHON) -c 'import json; print(json.dumps({"ok": True, "project": "$(PROJECT_ROOT)", "offline": True, "dry_run": True}, indent=2))'
