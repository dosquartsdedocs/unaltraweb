ARG BASE_MCP_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:6aa20cff86c3891a876e37ba0548fa36f3c5633c9f22ba672e9f50123d677cf6
FROM ${BASE_MCP_IMAGE}
ARG SOURCE_SNAPSHOT_SHA256
LABEL org.opencontainers.image.revision="sha256:${SOURCE_SNAPSHOT_SHA256}" \
      org.opencontainers.image.version="practice-editions-candidate" \
      io.context.unaltraweb.practice-candidate="editions-v1"
ADD source.tar.gz /opt/unaltraweb/
COPY packages/*.whl /tmp/practice-editions-candidate/
RUN python3 -m pip install --no-index --no-deps --force-reinstall --break-system-packages /tmp/practice-editions-candidate/*.whl \
    && python3 -m pip check \
    && rm /tmp/practice-editions-candidate/*.whl \
    && rmdir /tmp/practice-editions-candidate
WORKDIR /workspace
ENTRYPOINT ["unaltraweb-mcp"]
CMD ["--project", "/workspace", "mcp", "serve"]
