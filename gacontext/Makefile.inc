# @gacontext-owner: managed
# @gacontext-component: mcp-controls
# @gacontext-edit: upstream-only; local recipes belong in mcp/Makefile
# This is common build glue, not an implementation of the shared runtime/SDK.

.PHONY: gacontext-mcp-build gacontext-mcp-check gacontext-mcp-smoke gacontext-mcp-stdio

gacontext-mcp-build:
	+@$(MAKE) --no-print-directory --file=mcp/Makefile build

gacontext-mcp-check:
	+@$(MAKE) --no-print-directory --file=mcp/Makefile check

gacontext-mcp-smoke:
	+@$(MAKE) --no-print-directory --file=mcp/Makefile smoke

gacontext-mcp-stdio:
	+@$(MAKE) --no-print-directory --silent --file=mcp/Makefile stdio
