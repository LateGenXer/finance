# Contributing

## Branches

[lategenxer.streamlit.app](https://lategenxer.streamlit.app/) serves the tool from the `main`
branch.

## Getting started

### Locally

Install [uv](https://github.com/astral-sh/uv), then serve the calculator locally by running:

```shell
uv venv
uv pip install -r requirements-dev.txt
uv run streamlit run Home.py
```

This should start serving the tool locally.

### GitHub Codespaces

Follow these steps to open this sample in a Codespace:
1. Go to https://github.com/LateGenXer/finance
2. Click the **Code** drop-down menu.
3. Click on the **Codespaces** tab.
4. Click **Create codespace on main** .

This will serve personal instance of the tools on the cloud.

For more information on creating your codespace, visit the [GitHub documentation](https://docs.github.com/en/free-pro-team@latest/github/developing-online-with-codespaces/creating-a-codespace#creating-a-codespace).

### VS Code Dev Containers

If you have VS Code and Docker installed, you can click the badge above or [here](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/LateGenXer/finance) to get started. Clicking this link will cause VS Code to automatically install the Dev Containers extension if needed, clone the source code into a container volume, and spin up a dev container for use.

For more information on developing on VS Code with Dev Containers, visit [here](https://github.com/microsoft/vscode-remote-try-python/blob/main/README.md#vs-code-dev-containers)
