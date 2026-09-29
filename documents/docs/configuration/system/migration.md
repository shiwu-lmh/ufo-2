# Configuration Migration

UFO² supports the modular configuration directory `config/ufo/` and retains fallback support for older files under `ufo/config/`.

To use the modular layout, copy the provided templates and fill in the settings you need:

```powershell
Copy-Item config/ufo/agents.yaml.template config/ufo/agents.yaml
```

Keep machine-specific credentials in your local configuration. The loader merges YAML files under `config/ufo/` and allows environment-specific overrides such as `system_dev.yaml`.

Check the result with `python -m ufo.tools.validate_config ufo --show-config`.
