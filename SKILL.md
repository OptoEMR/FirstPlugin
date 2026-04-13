---
name: ni-python-instruments
description: >
  Generate correct, idiomatic Python code for NI (National Instruments) / Emerson Test & Measurement
  instrument drivers from the nimi-python ecosystem. Covers session management, instrument configuration,
  sourcing, measurement, sequencing, error handling, and test workflow patterns for SMUs, DMMs,
  oscilloscopes, switches, and signal generators. Use this skill whenever the user mentions nidcpower,
  nidmm, niscope, niswitch, nifgen, nise, nidigital, NI Python, nimi-python, SMU, source measure unit,
  DC power supply, PXI instrument, power supply control, PMIC validation, semiconductor test,
  instrument automation, or asks to write test scripts or measurement code involving NI hardware.
  Also trigger when the user asks about NI instrument session management, compliance limits,
  sequencing, LCR measurements, or fetch/measure patterns — even if they don't name a specific driver.
---

# NI Python Instruments Skill

This skill helps generate correct, production-quality Python code for NI modular instrument drivers
(the `nimi-python` family of packages). It prevents common AI code generation mistakes by encoding
the actual API patterns, enum names, session lifecycle, and measurement workflows from the official
NI Python API documentation.

## Why this skill exists

LLMs frequently hallucinate NI API details: inventing method names, using wrong enum values, 
misunderstanding the session state machine, or producing code that would fail silently on real hardware.
This skill provides ground-truth patterns so generated code works on first run.

## Supported Drivers

| Package     | Instrument Type              | Reference File             | Status    |
|-------------|------------------------------|----------------------------|-----------|
| nidcpower   | DC Power Supplies / SMUs     | references/nidcpower.md    | ✅ Active |
| nidmm       | Digital Multimeters          | references/nidmm.md        | ✅ Active |
| niscope     | Oscilloscopes / Digitizers   | references/niscope.md      | ✅ Active |
| nifgen      | Signal Generators / AWGs     | references/nifgen.md       | ✅ Active |
| niswitch    | Switches                     | references/niswitch.md     | ✅ Active |
| nidigital   | Digital Pattern Instruments  | references/nidigital.md    | ✅ Active |
| nise        | Switch Executive             | references/nise.md         | ✅ Active |

**When a user asks about a specific driver, read the corresponding reference file before generating code.**
If the driver's reference file doesn't exist yet, note this to the user and generate best-effort code
using the universal patterns below, which are shared across all nimi-python drivers.

## Universal Patterns (All nimi-python Drivers)

### Installation

All nimi-python driver packages follow the same naming convention and install via pip:

```
pip install nidcpower
pip install nidmm
pip install niscope
```

The NI driver runtime for the corresponding instrument must also be installed on the system
(available from ni.com/downloads). The Python package is a wrapper — it does not include the driver itself.

### Session Lifecycle

Every nimi-python driver uses the same session pattern. **Always use context managers** to ensure
proper resource cleanup, especially since instruments control real hardware with real voltages/currents.

```python
import nidcpower  # or nidmm, niscope, etc.

# CORRECT: Context manager ensures session closes even on error
with nidcpower.Session(resource_name="PXI1Slot2/0") as session:
    # configure, source, measure...
    pass
# Session is automatically closed, output disabled safely

# WRONG: Never do this — leaked sessions lock the instrument
session = nidcpower.Session(resource_name="PXI1Slot2/0")
# if an exception occurs here, the session is never closed
```

**Session constructor parameters** (common across drivers):
- `resource_name` (str, required): Instrument address, e.g. `"PXI1Slot2"`, `"PXI1Slot2/0"`, `"Dev1"`
- `channels` (str, optional): Channel selection, e.g. `"0"`, `"0,1"`, `"0-3"` (some drivers use resource_name for channel, e.g. `"PXI1Slot2/0"`)
- `reset` (bool, optional): If True, reset device to known state on open
- `options` (str, optional): Simulation and driver options, e.g. `"Simulate=1, DriverSetup=Model:4162; BoardType:PXIe"`

### Channel Indexing

Access specific channels using Python index notation on the session:

```python
# All channels (default when calling directly on session)
session.voltage_level = 5.0

# Specific channel(s)
session.channels["0"].voltage_level = 5.0
session.channels["0,1"].voltage_level = 5.0
session.channels[range(4)].measure_multiple()
```

### Programming State Machine

All NI instrument drivers follow a state machine:

```
Uncommitted → Committed → Running → Uncommitted (loop)
```

1. **Uncommitted**: Properties can be set freely. This is the state after `__init__()` or after modifying a property.
2. **Committed**: Call `session.commit()` to validate and apply settings. Required before reading computed properties like `measure_record_delta_time`.
3. **Running**: Call `session.initiate()` (use as context manager: `with session.initiate():`). The instrument is actively sourcing/measuring.

Modifying any property while in Committed or Running reverts to Uncommitted.

### Error Handling

```python
import nidcpower

try:
    with nidcpower.Session(resource_name="PXI1Slot2/0") as session:
        session.voltage_level = 5.0
        with session.initiate():
            measurements = session.fetch_multiple(count=10)
except nidcpower.errors.DriverError as e:
    print(f"NI driver error: {e}")
except nidcpower.errors.UnsupportedConfigurationError as e:
    print(f"Unsupported configuration: {e}")
except nidcpower.errors.DriverNotInstalledError as e:
    print(f"Driver not installed: {e}")
```

### Simulation Mode

For development/testing without hardware, use simulation:

```python
options = "Simulate=1, DriverSetup=Model:4162; BoardType:PXIe"
with nidcpower.Session(resource_name="PXI1Slot2/0", options=options) as session:
    # Code runs identically to real hardware but returns simulated values
    pass
```

## Test Workflow Patterns

### Pattern 1: Simple Source-and-Measure

The most common pattern: set a voltage/current, wait for settling, take a measurement.
Read the driver-specific reference file for the exact properties and enums.

### Pattern 2: Voltage/Current Sweep

Step through a range of values, measuring at each point. Use advanced sequences
for hardware-timed sweeps (more accurate) or Python loops for software-timed sweeps
(simpler, more flexible).

### Pattern 3: Multi-Channel Coordination

Configure multiple channels independently, initiate together, measure in parallel.
Use channel indexing to address subsets.

### Pattern 4: PMIC Validation Workflow

A semiconductor validation workflow for Power Management ICs typically involves:
1. Configure supply rails (voltage levels, current limits, sequencing)
2. Enable outputs in correct power-up sequence
3. Measure quiescent current (Iq) with high-resolution aperture
4. Sweep load conditions
5. Verify regulation under transient conditions
6. Power down in reverse sequence

### Pattern 5: Data Logging / Continuous Measurement

Use `fetch_multiple` in a loop with `fetch_backlog` to continuously acquire measurements
without gaps. The `measure_record_length` and `measure_record_length_is_finite` properties
control whether acquisition runs continuously or stops after N samples.

## Common Mistakes to Avoid

1. **Wrong enum values**: Always use the driver's enum classes (e.g., `nidcpower.OutputFunction.DC_VOLTAGE`), never raw strings or integers.
2. **Missing `initiate()`**: Measurements return stale or zero data if the session isn't in the Running state.
3. **Not using context managers**: Both for `Session()` and `initiate()`. Leaked sessions lock hardware.
4. **Ignoring compliance**: Always check `measurement.in_compliance` — if False, the output hit its limit and the measurement may be invalid.
5. **Wrong timeout**: `fetch_multiple` will raise a timeout error if the instrument hasn't completed sourcing. Calculate timeout from `source_delay + aperture_time`.
6. **Setting properties during Running state**: This silently reverts to Uncommitted. Reconfigure between `initiate()` calls, or use on-the-fly properties where supported.
7. **Using `measure()` when `fetch_multiple()` is needed**: `measure()` / `measure_multiple()` are for on-demand single-point reads. For sequenced or record-based acquisition, use `fetch_multiple()`.

## Integration with Test Frameworks

### pytest

```python
import pytest
import nidcpower

@pytest.fixture
def smu_session():
    """Fixture providing a configured SMU session."""
    options = "Simulate=1, DriverSetup=Model:4162; BoardType:PXIe"
    with nidcpower.Session(resource_name="PXI1Slot2/0", options=options) as session:
        session.source_mode = nidcpower.SourceMode.SINGLE_POINT
        session.output_function = nidcpower.OutputFunction.DC_VOLTAGE
        session.measure_when = nidcpower.MeasureWhen.AUTOMATICALLY_AFTER_SOURCE_COMPLETE
        yield session

def test_voltage_regulation(smu_session):
    """Verify DUT output voltage is within spec."""
    smu_session.voltage_level = 3.3
    smu_session.current_limit = 0.5
    with smu_session.initiate():
        measurements = smu_session.fetch_multiple(count=10)
    voltages = [m.voltage for m in measurements]
    assert all(3.2 < v < 3.4 for v in voltages), f"Voltage out of spec: {voltages}"
```

### Robot Framework

```robot
*** Settings ***
Library    NIDCPowerLibrary.py

*** Test Cases ***
Verify 3.3V Rail
    [Setup]    Open SMU Session    PXI1Slot2/0
    Configure DC Voltage    3.3    current_limit=0.5
    ${measurements}=    Measure Voltage    count=10
    Should Be Within Tolerance    ${measurements}    3.3    tolerance=0.1
    [Teardown]    Close SMU Session
```

## Adding a New Driver Reference

To add support for a new NI driver, create a reference file at `references/<driver_name>.md` with:

1. **Key enums and their values** (OutputFunction, MeasureWhen, SourceMode, etc.)
2. **Essential session properties** with types and valid ranges
3. **Core methods** with signatures and return types
4. **Canonical code examples** for the 3-5 most common workflows
5. **Driver-specific gotchas** that differ from the universal patterns above

Then update the Supported Drivers table in this file.
