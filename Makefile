PYTHON ?= python3
METRICS_ARGS ?=
SCIMAGO_INPUT ?=
DOCKER_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb:main
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

.PHONY: docs-build docs-serve docs-publish docs-down metrics-scimago-fetch metrics-update metrics-update-all metrics-check

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
