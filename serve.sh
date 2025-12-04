if ! command -v uv >/dev/null 2>&1; then
  echo "uv 未安装，请参考 https://docs.astral.sh/uv/getting-started/ 进行安装。" >&2
  exit 1
fi

uv sync --frozen
uv run python -m server.run_server "$@"
