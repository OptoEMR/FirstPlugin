---
name: measurement-plugin-sdk
description: >
  Create, scaffold, modify, or debug NI InstrumentStudio Measurement Plug-Ins using the
  ni-measurement-plugin-sdk Python framework. Use this skill whenever the user asks to create
  a new measurement plug-in, add inputs or outputs to an existing plug-in, author a .measui UI
  file, configure a .serviceconfig, set up a Poetry project for a plug-in, register a plug-in
  with the NI Discovery Service, implement streaming measurements, add cancellation support,
  integrate LLM calls, add function-calling tool execution, or asks about the measurement plug-in
  SDK, MeasurementService, @register_measurement, DataType, host_service, or any InstrumentStudio
  plug-in development topic.
---

# NI Measurement Plug-In SDK Skill

This skill encodes the complete, verified anatomy of an NI InstrumentStudio Measurement Plug-In
built with the `ni-measurement-plugin-sdk` Python framework. All patterns here have been validated
against the SDK examples at `SDK/` and the official GitHub repo at
https://github.com/ni/measurement-plugin-python.

---

## File Anatomy of a Plug-In

Every plug-in lives in its own directory and contains these files:

| File | Purpose |
|------|---------|
| `measurement.py` | Main service logic — **always run this to start the service** |
| `<Name>.serviceconfig` | JSON registration with the NI Discovery Service |
| `<Name>.measui` | InstrumentStudio UI layout (XML) |
| `<Name>.measproj` | UI Editor project file (XML, references the .measui) |
| `_helpers.py` | Shared logging + TestStand helpers (copy between plug-ins) |
| `pyproject.toml` | Poetry project + dependency declaration |
| `poetry.toml` | `in-project = true` so `.venv` stays local |
| `start.bat` | Discovery Service launch script |
| `install.bat` | Discovery Service install script (`poetry install --only main`) |
| `.env.sample` | Template for environment variables |
| `.serviceignore` | Excludes `.venv/`, `__pycache__/`, `.env` from deployment |

---

## measurement.py — Canonical Structure

```python
"""One-line description of what this plug-in measures."""

import logging
import pathlib
import sys

import click
import ni_measurement_plugin_sdk_service as nims
from _helpers import configure_logging, verbosity_option

# Resolves correctly whether running as .py or frozen .exe
script_or_exe = sys.executable if getattr(sys, "frozen", False) else __file__
service_directory = pathlib.Path(script_or_exe).resolve().parent

measurement_service = nims.MeasurementService(
    service_config_path=service_directory / "MyPlugin.serviceconfig",
    ui_file_paths=[service_directory / "MyPlugin.measui"],
)


@measurement_service.register_measurement
@measurement_service.configuration("Input Name", nims.DataType.Double, 1.0)
@measurement_service.output("Output Name", nims.DataType.Double)
def measure(input_value: float) -> tuple[float]:
    """Perform the measurement and return results."""
    logging.info("Executing measurement")
    result = input_value * 2.0
    return (result,)


@click.command
@verbosity_option
def main(verbosity: int) -> None:
    """Start the measurement service."""
    configure_logging(verbosity)
    with measurement_service.host_service():
        input("Press enter to close the measurement service.\n")


if __name__ == "__main__":
    main()
```

### Key rules
- `measurement_service` must be a module-level singleton — never create it inside a function.
- The `@register_measurement` decorator must come **first** (outermost), followed by `@configuration`
  decorators top-to-bottom matching function parameter order, then `@output` decorators.
- `measure()` must **return a tuple** even for a single output: `return (value,)`.
- Always use `with measurement_service.host_service():` — this registers with the Discovery Service
  and deregisters cleanly on exit.

---

## DataType Reference

```python
import ni_measurement_plugin_sdk_service as nims

# Scalar types
nims.DataType.Boolean       # bool
nims.DataType.Int32         # int
nims.DataType.UInt32        # int (unsigned)
nims.DataType.Int64         # int
nims.DataType.Float         # float (32-bit)
nims.DataType.Double        # float (64-bit)
nims.DataType.String        # str

# Array types
nims.DataType.BooleanArray1D
nims.DataType.Int32Array1D
nims.DataType.DoubleArray1D
nims.DataType.StringArray1D

# Special types
nims.DataType.Enum          # Python Enum or protobuf enum — requires enum_type=MyEnum
nims.DataType.DoubleXYData  # xydata_pb2.DoubleXYData — for graph outputs (streaming)
nims.DataType.Double2DArray # array_pb2.Double2DArray
nims.DataType.String2DArray # array_pb2.String2DArray

# Instrument resource (for pin-map based measurements)
nims.DataType.IOResourceArray1D  # list of pin names — requires instrument_type=
```

### Enum configuration example
```python
from enum import Enum

class Mode(Enum):
    FAST = 0
    ACCURATE = 1

@measurement_service.configuration("Mode", nims.DataType.Enum, Mode.FAST, enum_type=Mode)
@measurement_service.output("Mode Out", nims.DataType.Enum, enum_type=Mode)
def measure(mode: Mode) -> tuple[Mode]:
    return (mode,)
```

---

## Streaming Measurements (Generator Pattern)

When a measurement needs to update the UI progressively (chatbot, live graph, long-running sweep),
return a **generator** instead of a tuple. The SDK detects this automatically.

```python
import threading
from collections.abc import Generator

import grpc

@measurement_service.register_measurement
@measurement_service.configuration("Max Steps", nims.DataType.Int32, 10)
@measurement_service.output("Current Value", nims.DataType.Double)
@measurement_service.output("Step", nims.DataType.Int32)
def measure(max_steps: int) -> Generator[tuple[float, int], None, None]:
    """Streaming measurement — yields one result per step."""
    cancellation_event = threading.Event()
    measurement_service.context.add_cancel_callback(cancellation_event.set)

    for step in range(max_steps):
        if cancellation_event.is_set():
            measurement_service.context.abort(
                grpc.StatusCode.CANCELLED, "Client requested cancellation."
            )
        value = step * 1.5
        yield (value, step)     # Each yield pushes new values to the UI instantly
```

### Streaming rules
- Return type annotation must be `Generator[tuple[...], None, None]`.
- Always implement cancellation: `add_cancel_callback` + check the event each iteration.
- Use `measurement_service.context.abort(grpc.StatusCode.CANCELLED, "...")` to signal
  clean cancellation to InstrumentStudio.
- The `yield` tuple must match the declared `@output` count and order exactly.
- The SDK registers the measurement as `v2.MeasurementService` automatically when it detects
  a generator — only declare `v2` in the `.serviceconfig` `providedInterfaces`.

---

## Cancellation Pattern (Full)

```python
import threading
import time
import grpc

cancellation_event = threading.Event()
measurement_service.context.add_cancel_callback(cancellation_event.set)

# Inside a loop or wait:
while not done:
    if cancellation_event.is_set():
        measurement_service.context.abort(
            grpc.StatusCode.CANCELLED, "Client requested cancellation."
        )
    # ... do work ...
    time.sleep(0.1)
```

---

## .serviceconfig — JSON Registration

```json
{
  "services": [
    {
      "displayName": "My Plug-In (Py)",
      "version": "1.0.0",
      "serviceClass": "ni.examples.MyPlugin_Python",
      "descriptionUrl": "",
      "providedInterfaces": [
        "ni.measurementlink.measurement.v1.MeasurementService",
        "ni.measurementlink.measurement.v2.MeasurementService"
      ],
      "path": "start.bat",
      "installPath": "install.bat",
      "annotations": {
        "ni/service.description": "One-line description shown in InstrumentStudio.",
        "ni/service.collection": "Custom",
        "ni/service.tags": []
      }
    }
  ]
}
```

### Rules
- `serviceClass` must be globally unique — use a reverse-domain format: `org.team.PluginName_Python`.
- Use both `v1` and `v2` in `providedInterfaces` for non-streaming plug-ins. Use only `v2` for
  streaming (generator) plug-ins.
- `displayName` is what appears in InstrumentStudio's plug-in list.
- `path` is the filename of the startup script relative to the plug-in directory.
- `installPath` is the filename of the install script (run once to set up the venv).

---

## .measui — UI Layout (XML)

The `.measui` file is XML authored by the Measurement Plug-In UI Editor app. It can also be hand-
authored following the patterns below. Each control binds to a configuration or output channel via:

```
{ClientId}/Configuration/<parameter-display-name>   ← writable input control
{ClientId}/Output/<output-display-name>             ← read-only output indicator
```

The `ClientId` must match the `ClientId` attribute on the `<Screen>` element.
The `ServiceClass` on `<Screen>` must match the `.serviceconfig` `serviceClass`.

### Minimal measui skeleton

```xml
<?xml version="1.0" encoding="utf-8"?>
<SourceFile xmlns="http://www.ni.com/PlatformFramework">
  <SourceModelFeatureSet>
    <ParsableNamespace Name="http://www.ni.com/ConfigurationBasedSoftware.Core"
      FeatureSetName="Configuration Based Software Core"
      Version="9.8.1.49152" OldestCompatibleVersion="6.3.0.49152" />
    <ParsableNamespace Name="http://www.ni.com/InstrumentFramework/ScreenDocument"
      FeatureSetName="InstrumentStudio Measurement UI"
      Version="22.1.0.1" OldestCompatibleVersion="22.1.0.1" />
    <ParsableNamespace Name="http://www.ni.com/PanelCommon"
      FeatureSetName="Editor"
      Version="6.1.0.49152" OldestCompatibleVersion="6.1.0.0" />
  </SourceModelFeatureSet>
  <Screen ClientId="{YOUR-GUID-HERE}" DisplayName="My Plug-In (Py)"
    Id="unique-id-1" ServiceClass="ni.examples.MyPlugin_Python"
    xmlns="http://www.ni.com/InstrumentFramework/ScreenDocument">
    <ScreenSurface Height="[float]500" Width="[float]800" Left="[float]0" Top="[float]0"
      BackgroundColor="[SMSolidColorBrush]#00ffffff" PanelSizeMode="Fixed"
      Id="unique-id-2" xmlns="http://www.ni.com/ConfigurationBasedSoftware.Core">

      <!-- Numeric input -->
      <ChannelNumericText
        Channel="[string]{YOUR-GUID-HERE}/Configuration/Input Name"
        Id="unique-id-10" BaseName="[string]Numeric"
        Height="[float]24" Width="[float]160" Left="[float]20" Top="[float]36"
        Enabled="[bool]True" AdaptsToType="[bool]True"
        ValueType="[Type]Double" UnitAnnotation="[string]"
        Label="[UIModel]unique-id-11" />
      <Label Id="unique-id-11" LabelOwner="[UIModel]unique-id-10"
        Text="[string]Input Name" Left="[float]20" Top="[float]16"
        Height="[float]16" Width="[float]80"
        xmlns="http://www.ni.com/PanelCommon" />

      <!-- Numeric output (read-only) -->
      <ChannelNumericText
        Channel="[string]{YOUR-GUID-HERE}/Output/Output Name"
        Id="unique-id-20" BaseName="[string]Numeric"
        Height="[float]24" Width="[float]160" Left="[float]240" Top="[float]36"
        IsReadOnly="[bool]True" AdaptsToType="[bool]True"
        ValueType="[Type]Double" UnitAnnotation="[string]"
        Label="[UIModel]unique-id-21" />
      <Label Id="unique-id-21" LabelOwner="[UIModel]unique-id-20"
        Text="[string]Output Name" Left="[float]240" Top="[float]16"
        Height="[float]16" Width="[float]80"
        xmlns="http://www.ni.com/PanelCommon" />

    </ScreenSurface>
  </Screen>
</SourceFile>
```

### Control types and when to use each

| Control element | DataType | Enabled (input) | IsReadOnly (output) |
|----------------|----------|:---:|:---:|
| `ChannelNumericText` | Float, Double, Int32, UInt32 | ✓ | ✓ |
| `ChannelStringControl` | String | ✓ | ✓ |
| `ChannelCheckBox` | Boolean | ✓ | — |
| `ChannelLED` | Boolean | — | ✓ |
| `ChannelArrayViewer` | DoubleArray1D, StringArray1D | ✓ | ✓ |
| `ChannelEnumSelector` | Enum | ✓ | ✓ |
| `HmiGraphPlot` inside `ArrayGraph` | DoubleXYData | — | ✓ |

### Multi-line string control (text areas)
```xml
<ChannelStringControl
  Channel="[string]{GUID}/Configuration/User Message"
  AcceptsReturn="[bool]True"
  Height="[float]120" Width="[float]360"
  HorizontalScrollBarVisibility="[ScrollBarVisibility]Auto"
  VerticalScrollBarVisibility="[ScrollBarVisibility]Auto"
  Enabled="[bool]True"
  Id="ctrl-id" BaseName="[string]String"
  Left="[float]16" Top="[float]36"
  Label="[UIModel]label-id" Text="[string]" />
```
Use `AcceptsReturn="[bool]True"` for multi-line. Set both scroll bars to `Auto`.
For read-only outputs add `IsReadOnly="[bool]True"` and remove `Enabled`.

### Panel canvas (grouping box)
```xml
<ScreenSurfaceCanvas
  Id="canvas-id" BaseName="[string]Canvas"
  Height="[float]400" Width="[float]380"
  Left="[float]20" Top="[float]60"
  Background="[SMSolidColorBrush]#80808080"
  BackgroundColor="[SMSolidColorBrush]#ffe0e0e0"
  Label="[UIModel]canvas-label-id">
  <!-- child controls go here -->
</ScreenSurfaceCanvas>
<Label Id="canvas-label-id" LabelOwner="[UIModel]canvas-id"
  Text="[string]Section Title" Left="[float]20" Top="[float]40"
  Height="[float]16" Width="[float]100"
  xmlns="http://www.ni.com/PanelCommon" />
```

### Id and ClientId rules
- Every XML element needs a unique `Id`. Use UUID4 strings or sequential hex strings.
- The `ClientId` GUID on `<Screen>` is referenced in all channel binding strings.
- The `ServiceClass` on `<Screen>` must exactly match the `.serviceconfig` `serviceClass`.

---

## .measproj — Project File

The `.measproj` references one or more `.measui` files and is used by the Measurement Plug-In
UI Editor. It is not required by the runtime — only for editing the UI graphically.

```xml
<?xml version="1.0" encoding="utf-8"?>
<SourceFile xmlns="http://www.ni.com/PlatformFramework">
  <SourceModelFeatureSet>
    <ParsableNamespace Name="http://www.ni.com/InstrumentFramework/ScreenDocument"
      FeatureSetName="InstrumentStudio Measurement UI"
      Version="22.1.0.1" OldestCompatibleVersion="22.1.0.1" />
  </SourceModelFeatureSet>
  <Project xmlns="http://www.ni.com/PlatformFramework">
    <NameScopingEnvoy Id="envoy-1" ModelDefinitionType="DefaultTarget" Name="DefaultTarget">
      <DefaultTarget />
      <SourceFileReference Id="ref-1"
        ModelDefinitionType="{http://www.ni.com/InstrumentFramework/ScreenDocument}Screen"
        Name="MyPlugin.measui" StoragePath="MyPlugin.measui" />
    </NameScopingEnvoy>
  </Project>
</SourceFile>
```

---

## pyproject.toml — Poetry Project

```toml
[tool.poetry]
name = "my-plugin"
version = "1.0.0"
package-mode = false
description = "One-line description."
authors = ["Your Name"]

[tool.poetry.dependencies]
python = "^3.10"
ni-measurement-plugin-sdk-service = {version = ">=2.3.1,<4.0"}
click = ">=7.1.2, !=8.1.4"
# Add instrument drivers as needed:
# nidcpower = ">=1.4.0"
# nidmm = ">=1.4.0"
# niscope = ">=1.4.0"
# nifgen = ">=1.4.0"
# niswitch = ">=1.4.0"
# hightime = ">=0.2.1"   # required by nidcpower for timedelta arguments

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

**poetry.toml** (always include this alongside pyproject.toml):
```toml
[virtualenvs]
in-project = true
```

---

## Batch files

**start.bat** — Discovery Service uses this to launch the service:
```bat
@echo off
.venv\Scripts\python.exe measurement.py -v
```

**install.bat** — Discovery Service uses this to install deps:
```bat
@echo off
poetry install --only main
```

---

## _helpers.py — Standard Helpers

Copy this file between plug-ins unchanged. Provides:
- `configure_logging(verbosity: int)` — set up `basicConfig` based on `-v` count
- `verbosity_option` — click decorator for `--verbose / -v`
- `TestStandSupport` — class for TestStand sequence context integration

```python
"""Helper classes and functions for measurement plug-in services."""
from __future__ import annotations
import logging
import pathlib
from typing import Any, Callable, TypeVar
import click

def configure_logging(verbosity: int) -> None:
    level = logging.DEBUG if verbosity > 1 else logging.INFO if verbosity == 1 else logging.WARNING
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=level)

F = TypeVar("F", bound=Callable)

def verbosity_option(func: F) -> F:
    return click.option("-v", "--verbose", "verbosity", count=True,
                        help="Enable verbose logging.")(func)
```

---

## Setting Up and Running

```bat
REM 1. Install dependencies (creates .venv locally)
cd path\to\my-plugin
poetry install

REM 2. Run during development (auto-registers with Discovery Service)
poetry run python measurement.py -v

REM 3. Stop: press Enter in the terminal
```

For static registration (so InstrumentStudio discovers it automatically on startup):
1. Copy the plug-in directory to `C:\ProgramData\National Instruments\Plug-Ins\Measurements\`
2. **Do not copy `.venv`** — run `poetry install` in the new location
3. InstrumentStudio will discover and launch the service automatically

---

## Pin Map Integration (Instrument-Aware Plug-Ins)

For plug-ins that operate on hardware managed by InstrumentStudio's pin map:

```python
@measurement_service.configuration(
    "pin_names",
    nims.DataType.IOResourceArray1D,
    ["Pin1"],
    instrument_type=nims.session_management.INSTRUMENT_TYPE_NI_DCPOWER,
)
def measure(pin_names: list[str]) -> tuple[...]:
    with measurement_service.context.reserve_sessions(pin_names) as reservation:
        with reservation.initialize_nidcpower_sessions() as session_infos:
            for session_info in session_infos:
                ch = session_info.session.channels[session_info.channel_list]
                # configure ch ...
```

Available `initialize_*` methods on reservation:
- `initialize_nidcpower_sessions()`
- `initialize_nidmm_sessions()`
- `initialize_niscope_sessions()`
- `initialize_nifgen_sessions()`
- `initialize_niswitch_sessions()`
- `initialize_nidigital_sessions()`

---

## Common Mistakes to Avoid

1. **Wrong decorator order** — `@register_measurement` must be outermost. `@configuration` order
   must match function parameter order top-to-bottom. `@output` order matches return tuple index.

2. **Returning a value instead of a tuple** — Always `return (value,)` not `return value`.

3. **Creating `MeasurementService` inside `measure()`** — It must be module-level.

4. **Missing `host_service()`** — The service only registers with the Discovery Service (and
   becomes visible in InstrumentStudio) while inside `with measurement_service.host_service():`.

5. **Wrong `serviceClass`** — Must be identical between `.serviceconfig` and the `ServiceClass`
   attribute in the `.measui` `<Screen>` element. Any mismatch causes the UI to not bind.

6. **Id collisions in `.measui`** — Every element needs a unique `Id`. Duplicate IDs silently
   break channel bindings. Use sequential hex strings or UUID4 values.

7. **Forgetting `ClientId` in channel strings** — Channel format is
   `{ClientId}/Configuration/<name>` — omitting the GUID prefix breaks the binding silently.

8. **`v1` interface for streaming plug-ins** — Streaming (generator) plug-ins only work with
   `v2.MeasurementService`. Leave out `v1` from `providedInterfaces` in `.serviceconfig`.

9. **Holding a lock during I/O in streaming measurements** — Snapshot state under the lock,
   release it, then do network/instrument calls. Re-acquire to commit results. Holding a lock
   across a blocking call will deadlock with cancellation callbacks.

10. **NI driver package vs. NI driver runtime** — The Python packages (`nidcpower`, `nidmm`, etc.)
    are bindings only. The NI driver runtime (NI-DCPower, NI-DMM, etc.) must be installed
    separately from ni.com/downloads. Simulation mode also requires the runtime.

---

## Versioning

The SDK version in `pyproject.toml` determines the feature set:

| SDK version | InstrumentStudio version | Key features |
|-------------|--------------------------|-------------|
| `>=3.1.0`   | 2026 Q1+                 | Latest — use this for new plug-ins |
| `>=3.0.0`   | 2025 Q4+                 | |
| `>=2.3.0`   | 2025 Q2+                 | |
| `>=2.0.0`   | 2024 Q3+                 | Streaming measurements |

Use `ni-measurement-plugin-sdk-service = {version = ">=2.3.1,<4.0"}` to stay compatible across
a wide range of InstrumentStudio versions while allowing future minor updates.

---

## Quick Reference: Creating a New Plug-In from Scratch

1. Create a directory: `my-plugin/`
2. Copy `_helpers.py` from an existing plug-in
3. Create `pyproject.toml` and `poetry.toml` (see above)
4. Run `poetry install` to create `.venv`
5. Create `measurement.py` with `MeasurementService`, decorators, and `measure()` function
6. Create `MyPlugin.serviceconfig` with a unique `serviceClass`
7. Create `MyPlugin.measui` — match `ServiceClass` and `ClientId` to the `.serviceconfig`
8. Create `MyPlugin.measproj` referencing the `.measui`
9. Create `start.bat` and `install.bat`
10. Run `poetry run python measurement.py -v` and verify it appears in InstrumentStudio
