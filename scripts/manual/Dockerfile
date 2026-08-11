FROM python:3.13-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        fonts-dejavu-core \
        librsvg2-bin \
        pandoc \
        poppler-utils \
        texlive-fonts-recommended \
        texlive-lang-european \
        texlive-lang-spanish \
        texlive-latex-extra \
        texlive-xetex \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir PyYAML==6.0.2

COPY build_pdf.py /opt/unaltraweb/manual/build_pdf.py
COPY templates /opt/unaltraweb/manual/templates

ENTRYPOINT ["python3", "/opt/unaltraweb/manual/build_pdf.py"]
