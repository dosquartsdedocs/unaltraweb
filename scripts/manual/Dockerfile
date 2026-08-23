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

COPY build_pdf.py /opt/unaltraweb/manual/build_pdf.py
COPY Dockerfile /opt/unaltraweb/manual/Dockerfile
COPY templates /opt/unaltraweb/manual/templates

ENTRYPOINT ["python3", "/opt/unaltraweb/manual/build_pdf.py"]
