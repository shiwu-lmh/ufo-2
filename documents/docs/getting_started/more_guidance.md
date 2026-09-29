# More Guidance

## For users

Start with the [UFO² quick start](quick_start_ufo2.md), then configure your model and MCP servers in `config/ufo/`. Review the [core features](../ufo2/overview.md) and [FAQ](../faq.md) when you need more detail.

Task logs and screenshots are stored under `logs/<task-name>/`. You can validate the active configuration with:

```bash
python -m ufo.tools.validate_config ufo --show-config
```

## For developers

UFO²'s main implementation is in `ufo/`. Its AIP package provides shared client and service communication primitives. Begin with the [architecture overview](../infrastructure/agents/overview.md) and [MCP server tutorial](../tutorials/creating_mcp_servers.md).
