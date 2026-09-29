# Configuration Overview

UFO² loads modular YAML configuration from `config/ufo/`, with a legacy fallback to `ufo/config/`. The loader combines the files and exposes typed fields alongside dynamic access for additional settings.

| File | Purpose |
|---|---|
| `agents.yaml` | Model provider, endpoint, and agent settings |
| `system.yaml` | Runtime limits, logging, control backend, and evaluation settings |
| `rag.yaml` | Knowledge retrieval options |
| `mcp.yaml` | MCP servers available to each agent |
| `prices.yaml` | Model pricing for cost reporting |
| `third_party.yaml` | Optional external agent settings |

Example:

```python
from config.config_loader import get_ufo_config

config = get_ufo_config()
max_step = config.system.max_step
api_model = config.app_agent.api_model
```

The `ConfigLoader` merges YAML files in `config/ufo/`; environment-specific files such as `system_dev.yaml` can override base values. Validate settings with `python -m ufo.tools.validate_config ufo --show-config`. See the [configuration migration guide](migration.md) for legacy-path details.
