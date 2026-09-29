# FAQ

## Which component should I use?

Use UFO² for Windows desktop automation across applications. This workspace no longer contains the UFO³ Galaxy orchestration implementation.

## Where do I configure model access?

Configure the agent API settings in `config/ufo/agents.yaml` and system behavior in `config/ufo/system.yaml`. Keep API keys in local configuration and do not share them in logs.

## Where are task logs saved?

Task logs and screenshots are written under `logs/<task-name>/`.

## How do I validate configuration?

From the repository root, run `python -m ufo.tools.validate_config ufo --show-config`.

## Where can I find setup instructions?

See the [UFO² quick start](getting_started/quick_start_ufo2.md) and [configuration overview](configuration/system/overview.md).
