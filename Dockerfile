FROM --platform=linux/amd64 ghcr.io/owl-corp/python-poetry-base:3.12-slim

# Install build dependencies
RUN apt-get update && apt-get install -y libmagickwand-dev && apt autoclean && rm -rf /var/lib/apt/lists/*

# Install project dependencies
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["-m", "arthur"]
