ARG python_version=3.13-slim

FROM --platform=linux/amd64 ghcr.io/owl-corp/python-poetry-base:$python_version AS wheel-builder

# Install build dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libldap2-dev \
    libsasl2-dev \
    gcc \
    heimdal-dev \
    && apt autoclean && rm -rf /var/lib/apt/lists/*

# Install project dependencies with build tools available
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --without dev --with ldap

# -------------------------------------------------------------------------------

FROM --platform=linux/amd64 ghcr.io/owl-corp/python-poetry-base:$python_version

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libmagickwand-dev \
    libldap2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies from build cache
WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY --from=wheel-builder /opt/poetry/cache /opt/poetry/cache
RUN poetry install --no-root --without dev --with ldap

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["-m", "arthur"]
