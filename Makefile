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

.PHONY: docs-build docs-serve docs-publish docs-down metrics-scimago-fetch metrics-update metrics-update-all metrics-check manual-pdf-image manual-pdf-status manual-pdf-build manual-pdf-publish
.PHONY: mcp-build mcp-init mcp-check mcp-smoke mcp-stdio mcp-list-tools mcp-starter-templates mcp-initialize-site mcp-site-context mcp-profile-check mcp-manual-source-quality-check mcp-manual-editorial-quality-check mcp-manual-authoring-capabilities mcp-manual-pdf-status mcp-manual-pdf-build mcp-manual-pdf-publish mcp-profile-prune-plan mcp-profile-prune mcp-content-inventory mcp-language-policy mcp-content-approval-inventory mcp-translation-plan mcp-bibliography-inventory mcp-bibliometrics-check mcp-build-health

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

manual-pdf-image: ## Build the isolated local Pandoc/XeLaTeX image
	docker build -f scripts/manual/Dockerfile -t "$(MANUAL_PDF_IMAGE)" scripts/manual

manual-pdf-status: manual-pdf-image ## Inspect manual PDF configuration and artefacts
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" status --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

manual-pdf-build: manual-pdf-image ## Build manual PDFs and cover previews under tmp
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" build --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",)

manual-pdf-publish: manual-pdf-image ## Copy built PDF artefacts to configured public paths
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(abspath $(PROJECT)):/project" -w /project "$(MANUAL_PDF_IMAGE)" publish --project /project $(if $(strip $(MANUAL_PDF_LANG)),--language "$(MANUAL_PDF_LANG)",) $(if $(filter 1 true TRUE yes YES y Y,$(MANUAL_PDF_PUBLISH_DRY_RUN)),--dry-run,)

docs-build:
	docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -e BUNDLE_GEMFILE=docs/Gemfile -e BUNDLE_APP_CONFIG=/work/tmp/docs_bundle_config -e BUNDLE_PATH=/work/tmp/docs_bundle_path -v "$(CURDIR):/work" -w /work $(DOCKER_IMAGE) bash -lc 'git config --global --add safe.directory /work >/dev/null 2>&1 || true; mkdir -p tmp/docs_bundle_config tmp/docs_bundle_path; bundle check || bundle install; core_config=$$(bundle exec ruby -e "spec = Gem::Specification.find_by_name(\"unaltraweb\"); print File.join(spec.full_gem_path, \"_config.yml\")"); bundle exec jekyll build --source docs --destination tmp/docs-site --config "$$core_config,docs/_config.yml" --disable-disk-cache'

docs-serve:
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
