# https://github.com/devcontainers/images/tree/main/src/python
FROM mcr.microsoft.com/devcontainers/python:3.12

# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER vscode
env HOME=/home/vscode

ENV UV_NO_ENV_FILE=1

# https://www.rhosignal.com/posts/uv-in-docker/
ENV UV_PROJECT_ENVIRONMENT="$HOME/venv"
RUN uv venv --prompt devcontainer "$UV_PROJECT_ENVIRONMENT"

ENV VIRTUAL_ENV="$HOME/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# https://discuss.streamlit.io/t/streamlit-showing-me-welcome-to-streamlit-message-when-executing-it-with-docker/26168
# https://www.docker.com/blog/introduction-to-heredocs-in-dockerfiles/
COPY <<EOF $HOME/.streamlit/credentials.toml
[general]
email = ""
EOF
