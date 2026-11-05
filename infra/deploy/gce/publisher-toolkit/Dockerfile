# Owner supplies an independently accepted immutable Debian12 runtime base.
# Build context is this directory plus the pinned Node archive obtained out of band.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY node-v22.23.4-linux-x64.tar.xz /tmp/node.tar.xz
RUN echo '1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce  /tmp/node.tar.xz' | sha256sum -c - \
 && tar -xJf /tmp/node.tar.xz --strip-components=1 -C /usr/local \
 && rm /tmp/node.tar.xz \
 && echo '94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90  /usr/local/bin/node' | sha256sum -c - \
 && test "$(node --version)" = v22.23.4
WORKDIR /opt/autodata/publisher-toolkit
COPY package.json package-lock.json ./
# The unchanged lock is the only dependency selection; npm runs only at build time.
# Bin links are disabled because the runtime tree rejects all symbolic links.
RUN npm ci --ignore-scripts --bin-links=false --no-audit --no-fund
COPY build_tree.mjs /usr/local/lib/autodata/build_tree.mjs
RUN node /usr/local/lib/autodata/build_tree.mjs
# No authority or acceptance is manufactured here: the exact installed-tree and
# license inventory hashes require a separately owner-signed dependency review.
# Runtime caller must set --read-only and mount trust/control/tool pins read-only.
ENV PATH=/usr/local/bin:/usr/bin:/bin
ENTRYPOINT ["/usr/bin/python3", "-I", "/control/infra/deploy/gce/publisher_cli.py"]
