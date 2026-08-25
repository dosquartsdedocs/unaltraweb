LOCAL_CORE ?= /opt/unaltraweb
LOCAL_GEMFILE := tmp/Gemfile.local

.PHONY: local-gemfile build-native serve-native build serve clean

local-gemfile:
	@mkdir -p tmp
	@printf '%s\n' 'source "https://rubygems.org"' 'gem "unaltraweb", path: "$(LOCAL_CORE)"' > $(LOCAL_GEMFILE)

build-native: local-gemfile
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll build --config $(LOCAL_CORE)/_config.yml,_config.yml --disable-disk-cache

serve-native: local-gemfile
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle lock --local
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle check
	@BUNDLE_GEMFILE=$(LOCAL_GEMFILE) bundle exec jekyll serve --config $(LOCAL_CORE)/_config.yml,_config.yml --host $${HOST:-0.0.0.0} --port $${PORT:-4000} --disable-disk-cache

build: build-native

serve: serve-native

clean:
	@rm -rf _site tmp .jekyll-cache
