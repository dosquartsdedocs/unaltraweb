ARG BASE_MCP_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6
FROM ${BASE_MCP_IMAGE}

ARG SOURCE_SHA
LABEL org.opencontainers.image.revision="${SOURCE_SHA}" \
      org.opencontainers.image.version="practice-candidate-${SOURCE_SHA}" \
      io.context.unaltraweb.practice-candidate="source-slice-v1"

# The archive is the approved Git revision, not the caller's working directory.
ADD source.tar.gz /opt/unaltraweb/
COPY packages/unaltraweb_mcp-0.7.1-py3-none-any.whl /tmp/practice-candidate/
RUN python3 -m pip install --no-index --no-deps --force-reinstall --break-system-packages \
      /tmp/practice-candidate/unaltraweb_mcp-0.7.1-py3-none-any.whl \
    && rm /tmp/practice-candidate/unaltraweb_mcp-0.7.1-py3-none-any.whl \
    && rmdir /tmp/practice-candidate

WORKDIR /workspace
ENTRYPOINT ["unaltraweb-mcp"]
CMD ["--project", "/workspace", "mcp", "serve"]
