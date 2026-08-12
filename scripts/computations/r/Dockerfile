FROM ghcr.io/quarto-dev/quarto:1.10.18 AS quarto

FROM rocker/geospatial:4.6.1

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=quarto /opt/quarto /opt/quarto-1.10.18

RUN for sources in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
        if test -f "$sources"; then \
          sed -i \
            -e 's|http://deb.debian.org|https://deb.debian.org|g' \
            -e 's|http://security.debian.org|https://security.debian.org|g' \
            -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
            -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
            "$sources"; \
        fi; \
      done \
    && ln -sf /opt/quarto-1.10.18/bin/quarto /usr/local/bin/quarto \
    && apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-yaml \
    && rm -rf /var/lib/apt/lists/* \
    && install2.r --error --skipinstalled \
        jsonlite \
        knitr \
        renv \
        rmarkdown

COPY scripts/computations/render.py /opt/unaltraweb/computations/render.py

CMD ["quarto", "check", "knitr"]
