LOCAL_CORE ?= /opt/unaltraweb
LOCAL_GEMFILE := tmp/Gemfile.local
MCP_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.3.0
UNALTRAWEB_CAPTURE_RUNTIME := 1
LOCAL_UID ?= $(shell id -u)
LOCAL_GID ?= $(shell id -g)
PORT ?= 4000
CONTAINER ?= unaltraweb-site-$(shell printf '%s' '$(CURDIR)' | cksum | cut -d' ' -f1)

.PHONY: local-gemfile site-check-native build-native serve-capture-native serve-native test-native build serve test down clean

local-gemfile:
	@mkdir -p tmp
	@printf '%s\n' 'source "https://rubygems.org"' 'gem "unaltraweb", path: "$(LOCAL_CORE)"' > $(LOCAL_GEMFILE)

site-check-native:
	@unaltraweb-mcp --project "$(CURDIR)" mcp site-check >/dev/null

build-native: local-gemfile site-check-native
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll build --config $(LOCAL_CORE)/_config.yml,_config.yml --disable-disk-cache

serve-capture-native: local-gemfile
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll serve --config $(LOCAL_CORE)/_config.yml,_config.yml --host $${HOST:-0.0.0.0} --port $${PORT:-4000} --disable-disk-cache

serve-native: site-check-native serve-capture-native

test-native: build-native

build:
	@docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(CURDIR):/workspace" -w /workspace --entrypoint make "$(MCP_IMAGE)" --silent build-native LOCAL_CORE=/opt/unaltraweb

serve:
	@docker run --rm --name "$(CONTAINER)" --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -p "$(PORT):$(PORT)" -v "$(CURDIR):/workspace" -w /workspace --entrypoint make "$(MCP_IMAGE)" --silent serve-native LOCAL_CORE=/opt/unaltraweb HOST=0.0.0.0 PORT="$(PORT)"

test:
	@docker run --rm --user "$(LOCAL_UID):$(LOCAL_GID)" -e HOME=/tmp -v "$(CURDIR):/workspace" -w /workspace --entrypoint make "$(MCP_IMAGE)" --silent test-native LOCAL_CORE=/opt/unaltraweb

down:
	@container="$$(docker ps -aq --filter "name=^/$(CONTAINER)$$")"; if test -n "$$container"; then docker rm -f "$$container" >/dev/null; fi

clean:
	@rm -rf _site tmp .jekyll-cache
