FROM ghcr.io/quarto-dev/quarto:1.10.18 AS quarto

FROM python:3.13-slim-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

COPY --from=quarto /opt/quarto /opt/quarto

RUN ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto \
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && python3 -m pip install --no-cache-dir \
        geopandas==1.1.1 \
        ipykernel==6.30.1 \
        jupyter==1.1.1 \
        jupyter-cache==1.0.1 \
        matplotlib==3.10.5 \
        numpy==2.3.2 \
        pandas==2.3.1 \
        PyYAML==6.0.2 \
        pyproj==3.7.1 \
        shapely==2.1.1 \
    && rm -rf /var/lib/apt/lists/*

ENV QUARTO_PYTHON=/usr/local/bin/python3

COPY scripts/computations/render.py /opt/unaltraweb/computations/render.py

CMD ["quarto", "check", "jupyter"]
