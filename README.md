# Expediente Vivo

Foundation slice for the local markdown workspace and filesystem invariants.

## Run tests

```bash
python -m pytest
```

## Run the desktop dashboard

```bash
pip install -e .[desktop]
expediente
```

By default the local workspace is created at `./expedientes`. Override it with:

```bash
export EXPEDIENTE_WORKSPACE_ROOT=/path/to/expedientes
```

Future model-backed agents will read provider settings from:

```bash
export EXPEDIENTE_MODEL_PROVIDER=openai
export EXPEDIENTE_MODEL_API_KEY=...
export EXPEDIENTE_MODEL_NAME=...
```

## Current scope

- bootstrap the `expedientes/` workspace
- create patient directories safely
- enforce consultation file naming conventions
- append patient log entries without mutating existing entries
- start a minimal PySide6 desktop shell
- validate the future model API gateway configuration

## Not included yet

- medical agents and orchestration flows
