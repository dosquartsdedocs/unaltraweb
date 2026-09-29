# Acceptance overlay: retain the released Ruby/gem inventory, install final controls.
ARG BASE_IMAGE=ghcr.io/dosquartsdedocs/unaltraweb-mcp@sha256:36d17edbade77edb40a687f6a744203c6329acb33fbc2eb255e88d9ff1a42c98
FROM ${BASE_IMAGE}
COPY . /opt/unaltraweb
COPY --from=wheel / /tmp/acceptance-wheel/
RUN python3 -m pip install --no-deps --no-index --break-system-packages /tmp/acceptance-wheel/*.whl
