ARG python_version=3.14-slim

FROM python:$python_version AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/

ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# Install build dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    heimdal-dev \
    xz-utils \
    && apt autoclean && rm -rf /var/lib/apt/lists/*

# Install project dependencies with build tools available
WORKDIR /opt/king-arthur
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --frozen --no-install-project --extra ldap --extra voice --no-group dev

# Download and extract static ffmpeg binaries
ADD https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-04-12-13-04/ffmpeg-n7.1.3-43-g5a1f107b4c-linux64-gpl-7.1.tar.xz /tmp/ffmpeg.tar.xz
RUN tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ \
    && mv /tmp/ffmpeg-n7.1.3-43-g5a1f107b4c-linux64-gpl-7.1/bin/ffmpeg /usr/local/bin/ffmpeg \
    && rm -rf /tmp/ffmpeg*

# -------------------------------------------------------------------------------

FROM python:$python_version

# Create user 1000 so that the runAsUser has a username
RUN useradd kingarthur -u 1000 -m

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    imagemagick \
    libldap2 \
    && rm -rf /var/lib/apt/lists/* /var/cache/debconf/*

COPY --from=builder /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg

# Install dependencies from build cache
# .venv not put in /app so that it doesn't conflict with the dev
# volume we use to avoid rebuilding image every code change locally
COPY --from=builder /opt/king-arthur/.venv /opt/king-arthur/.venv

# Copy the source code in last to optimize rebuilding the image
WORKDIR /app
COPY . .
ENV PATH="/opt/king-arthur/.venv/bin:$PATH"

ENTRYPOINT ["python"]
CMD ["-m", "arthur"]
