FROM python:3.13-slim-trixie@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a

ENV DEBIAN_FRONTEND=noninteractive
ARG DEBIAN_SNAPSHOT=20260822T000000Z

RUN printf '%s\n' \
        "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}/ trixie main" \
        "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}/ trixie-security main" \
        > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-dejavu-core \
        librsvg2-bin \
        pandoc \
        poppler-utils \
        qpdf \
        texlive-fonts-recommended \
        texlive-lang-european \
        texlive-lang-spanish \
        texlive-latex-extra \
        texlive-xetex \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir PyYAML==6.0.2

RUN pip install --no-cache-dir 'pypdf>=6,<7' 'markdown-it-py>=3,<5'
COPY scripts/manual/build_pdf.py /opt/unaltraweb/manual/build_pdf.py
COPY scripts/manual/Dockerfile /opt/unaltraweb/manual/Dockerfile
COPY scripts/manual/filters /opt/unaltraweb/manual/filters
COPY scripts/manual/templates /opt/unaltraweb/manual/templates
COPY src/unaltraweb_mcp/__init__.py src/unaltraweb_mcp/distribution.py src/unaltraweb_mcp/component-contract.json src/unaltraweb_mcp/component-contract.schema.json src/unaltraweb_mcp/artifact_handoff_v1.py src/unaltraweb_mcp/artifact-handoff-v1.schema.json src/unaltraweb_mcp/artifact_imports.py src/unaltraweb_mcp/letter_bundle.py src/unaltraweb_mcp/pdf_probe.py src/unaltraweb_mcp/processes.py /opt/unaltraweb/src/unaltraweb_mcp/
ENV PYTHONPATH=/opt/unaltraweb/src

ENTRYPOINT ["python3", "/opt/unaltraweb/manual/build_pdf.py"]
