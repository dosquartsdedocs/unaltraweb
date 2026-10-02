# Test-only worker selection; package/core bytes come from the selected MCP image.
ARG MCP_IMAGE=unaltraweb-import-80-mcp:dev
FROM ${MCP_IMAGE}
ARG PDF_IMAGE=unaltraweb-import-80-pdf:dev
ENV MANUAL_PDF_IMAGE=${PDF_IMAGE}
