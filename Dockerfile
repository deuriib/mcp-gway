# syntax=docker/dockerfile:1
#
# mcp-gway — multistage container build (builder → test → runtime [+ dev]).
#
# Toolchain (python/uv/node) is installed by mise from `mise.toml` + `mise.lock`,
# the project's single source of truth for tool versions. Base images are pinned
# by digest. To refresh:
#   docker buildx imagetools inspect ghcr.io/jdx/mise:2026.10.25-debian
#   docker buildx imagetools inspect debian:13-slim
#
# glibc (Debian) bases are used deliberately: `starlark-pyo3` ships only
# manylinux wheels (no musllinux), so Alpine would force a Rust build.

ARG MISE_IMAGE=ghcr.io/jdx/mise:2026.10.25-debian@sha256:00a8a9d05a300e5a15a89d6d3a87ea88ec4e78c4702b78d49aa1d3250af61427
ARG RUNTIME_IMAGE=debian:13-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4
# Must match `[tools].python` in mise.toml / mise.lock — the runtime copies the
# mise-managed CPython from this path so the builder venv's symlinks resolve.
ARG PYTHON_VERSION=3.12.14
# Major.minor of PYTHON_VERSION; keep both in sync when bumping Python.
ARG PYTHON_SERIES=3.12

###############################################################################
# builder — mise installs the toolchain, uv builds the project into /opt/venv
###############################################################################
FROM ${MISE_IMAGE} AS builder
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

# Layer 1: toolchain — cached until mise.toml / mise.lock change.
COPY mise.toml mise.lock ./
RUN mise trust && mise install --locked

# Layer 2: production deps only (caches independently of source edits).
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN mise exec -- uv sync --frozen --no-dev --no-install-project

# Layer 3: build + install the project itself into /opt/venv. `--no-editable`
# is required so the package lands in site-packages instead of a .pth pointing
# at /app/src (which is not copied into the runtime stage).
COPY src ./src
RUN mise exec -- uv sync --frozen --no-dev --no-editable

# Trim dev/GUI artifacts from the standalone CPython before the runtime copies
# it. Docker layers are additive, so trimming here (not in `runtime`) is what
# actually shrinks the final image. The interpreter is a static build, so
# libpython*.so (embedding only), headers, docs, Tcl/Tk and the base
# pip/setuptools are unused at runtime.
ARG PYTHON_VERSION
ARG PYTHON_SERIES
# Fail fast if PYTHON_SERIES drifts from PYTHON_VERSION — otherwise the paths
# below are silent no-ops and the fat image ships unnoticed.
RUN test -d /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES} \
    && rm -rf \
    /mise/installs/python/${PYTHON_VERSION}/include \
    /mise/installs/python/${PYTHON_VERSION}/share \
    /mise/installs/python/${PYTHON_VERSION}/lib/libpython3*.so* \
    /mise/installs/python/${PYTHON_VERSION}/lib/tcl* \
    /mise/installs/python/${PYTHON_VERSION}/lib/tk* \
    /mise/installs/python/${PYTHON_VERSION}/lib/itcl* \
    /mise/installs/python/${PYTHON_VERSION}/lib/thread3* \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/tkinter \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/idlelib \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/ensurepip \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/lib2to3 \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/pydoc_data \
    /mise/installs/python/${PYTHON_VERSION}/lib/python${PYTHON_SERIES}/site-packages

###############################################################################
# test — full source + dev/test deps; runs pytest (CI parity)
###############################################################################
FROM ${MISE_IMAGE} AS test
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

COPY mise.toml mise.lock ./
RUN mise trust && mise install --locked

# Full repo: tests read scripts/, plugins/, plugin.json, package*.json, rules/,
# .pi/, README.md and AGENTS.md (see tests/test_version_surfaces.py).
COPY . .
RUN mise exec -- uv sync --frozen --all-groups --no-editable

CMD ["pytest", "-v"]

###############################################################################
# dev — editable install + watchfiles/debugpy for hot-reload (compose.dev.yml)
###############################################################################
FROM ${MISE_IMAGE} AS dev
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

COPY mise.toml mise.lock ./
RUN mise trust && mise install --locked

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN mise exec -- uv sync --frozen --no-dev --editable \
    && mise exec -- uv pip install --python /opt/venv/bin/python watchfiles debugpy

# watchfiles restarts the gateway whenever a source file under /app/src changes.
CMD ["watchfiles", "--filter", "python", "mcp-gway serve --transport http --host 0.0.0.0 --port 8080", "/app/src"]

###############################################################################
# runtime — minimal, non-root (uid 1000), read-only FS (enforced in compose)
###############################################################################
FROM ${RUNTIME_IMAGE} AS runtime
ARG PYTHON_VERSION

# The mise-installed CPython is an astral python-build-standalone build, which is
# relocatable — copied here so the builder's venv interpreter symlinks resolve
# unchanged (no re-binding). ca-certificates is required for HTTPS (remote MCP
# servers + OAuth).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/gateway

COPY --from=builder /mise/installs/python/${PYTHON_VERSION} /mise/installs/python/${PYTHON_VERSION}
COPY --from=builder /opt/venv /opt/venv

# Non-root user (uid 1000) + config home. The config volume is mounted at
# /home/gateway/.config/mcp-gway by docker-compose.yml.
RUN groupadd --gid 1000 gateway \
    && useradd --uid 1000 --gid gateway --home-dir /home/gateway --create-home --shell /bin/sh gateway \
    && mkdir -p /home/gateway/.config/mcp-gway/servers /home/gateway/.config/mcp-gway/tokens \
    && chown -R gateway:gateway /home/gateway

WORKDIR /home/gateway
USER gateway:gateway

EXPOSE 8080

# Binds 0.0.0.0 inside the container so the published host port is reachable.
# This REQUIRES MCP_GWAY_ALLOW_REMOTE=1 (set in docker-compose.yml); without it
# the gateway exits 2 rather than exposing itself (fail-closed, see AGENTS.md).
ENTRYPOINT ["mcp-gway"]
CMD ["serve", "--transport", "http", "--host", "0.0.0.0", "--port", "8080"]
