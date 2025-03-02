ARG python_version=3.13-slim

FROM python:$python_version AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# Install build dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    heimdal-dev \
    && apt autoclean && rm -rf /var/lib/apt/lists/*

# Install project dependencies with build tools available
WORKDIR /opt/king-arthur
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --extra ldap --no-group dev

# -------------------------------------------------------------------------------

FROM python:$python_version

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libmagickwand-dev \
    libldap2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies from build cache
WORKDIR /app
COPY --from=builder /opt/king-arthur/.venv /opt/king-arthur/.venv

# Copy the source code in last to optimize rebuilding the image
COPY . .
ENV PATH="/opt/king-arthur/.venv/bin:$PATH"

ENTRYPOINT ["python"]
CMD ["-m", "arthur"]
