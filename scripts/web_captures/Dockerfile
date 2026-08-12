FROM mcr.microsoft.com/playwright@sha256:f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a

RUN rm -f /etc/apt/sources.list.d/nodesource.list \
    && for sources in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do \
      if test -f "$sources"; then \
        sed -i \
          -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
          -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
          "$sources"; \
      fi; \
    done \
    && apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-yaml \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/unaltraweb/scripts/web_captures

COPY scripts/web_captures/package.json scripts/web_captures/package-lock.json ./
RUN npm ci --omit=dev

COPY scripts/web_captures/capture.mjs ./capture.mjs
COPY scripts/web_captures/render.py ./render.py
COPY scripts/web_captures/Dockerfile ./Dockerfile
COPY _config.yml /opt/unaltraweb/_config.yml
COPY _plugins /opt/unaltraweb/_plugins
COPY _layouts /opt/unaltraweb/_layouts
COPY _includes /opt/unaltraweb/_includes
COPY _sass /opt/unaltraweb/_sass
COPY assets/js /opt/unaltraweb/assets/js

ENTRYPOINT ["node", "/opt/unaltraweb/scripts/web_captures/capture.mjs"]
