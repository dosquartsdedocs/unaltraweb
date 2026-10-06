# Installed Docker profile. No core source, Python runtime or image build here.
MCP_RELEASE_IMAGE ?= ghcr.io/dosquartsdedocs/unaltraweb-mcp:0.7.1
override MCP_RELEASE_IMAGE := $(value MCP_RELEASE_IMAGE)
export MCP_RELEASE_IMAGE

ifneq ($(filter mcp-stdio,$(MAKECMDGOALS)),)
ifneq ($(origin MCP_CONSUMER_WORKSPACE),environment)
ifneq ($(origin MCP_CONSUMER_WORKSPACE),environment override)
$(error MCP_CONSUMER_WORKSPACE must be inherited through the process environment)
endif
endif
endif

.PHONY: mcp-build mcp-check mcp-smoke mcp-stdio mcp-down

mcp-build:
	@exec /bin/sh ./scripts/unaltraweb-mcp-bootstrap.sh --image "$$MCP_RELEASE_IMAGE" --prepare

mcp-check:
	@exec /bin/sh ./scripts/unaltraweb-mcp-bootstrap.sh --image "$$MCP_RELEASE_IMAGE" --check

mcp-smoke:
	@exec /bin/sh ./scripts/unaltraweb-mcp-bootstrap.sh --image "$$MCP_RELEASE_IMAGE" --smoke

mcp-stdio:
	@test -n "$${MCP_CONSUMER_WORKSPACE:-}" || { printf '%s\n' 'MCP_CONSUMER_WORKSPACE is required' >&2; exit 2; }
	@exec /bin/sh ./scripts/unaltraweb-mcp-bootstrap.sh --image "$$MCP_RELEASE_IMAGE"

mcp-down:
	@exec /bin/sh ./scripts/unaltraweb-mcp-cleanup.sh
