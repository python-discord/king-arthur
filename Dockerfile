ARG python_version=3.12-slim

FROM --platform=linux/amd64 ghcr.io/owl-corp/python-poetry-base:$python_version AS wheel-builder

# Install build dependencies
RUN apt-get update && apt-get install --no-install-recommends -y libldap2-dev libsasl2-dev gcc && apt autoclean && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./

# Only the LDAP group has deps that requires gcc, so only build that for now
RUN poetry install --only ldap --no-root

FROM --platform=linux/amd64 ghcr.io/owl-corp/python-poetry-base:$python_version

RUN apt-get update && apt-get install --no-install-recommends -y libmagickwand-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built LDAP group from the build stage that required gcc
COPY --from=wheel-builder /opt/poetry/cache /opt/poetry/cache

# Install the rest of the dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --with ldap --no-root

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["-m", "arthur"]
