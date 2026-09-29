# UFO² Configuration Tools

These commands operate on the UFO² configuration under `config/ufo/`.

## Validate configuration

```bash
python -m ufo.tools.validate_config ufo --show-config
```

## Migrate a legacy configuration

```bash
python -m ufo.tools.migrate_config
```

The loader reads modular YAML files from `config/ufo/` and supports legacy files in `ufo/config/`. Keep API keys in local configuration and avoid sharing them in command output or logs.
