FROM --platform=linux/amd64 ghcr.io/chrislovering/python-poetry-base:3.11-slim

# Install project dependencies
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev

# Set Git SHA environment variable for Sentry
ARG git_sha="development"
ENV GIT_SHA=$git_sha

# Copy the source code in last to optimize rebuilding the image
COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["-m", "arthur"]
