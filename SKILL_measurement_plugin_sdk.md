---
name: measurement-plugin-sdk
description: >
  Create, scaffold, modify, or debug NI InstrumentStudio Measurement Plug-Ins using the
  ni-measurement-plugin-sdk Python framework. Use this skill whenever the user asks to create
  a new measurement plug-in, add inputs or outputs to an existing plug-in, author a .measui UI
  file, configure a .serviceconfig, set up a Poetry project for a plug-in, register a plug-in
  with the NI Discovery Service, implement streaming measurements, add cancellation support,
  integrate LLM/AI calls, add OpenAI function-calling tool execution, or asks about
  MeasurementService, @register_measurement, DataType, host_service, streaming generators,
  pin maps, or any InstrumentStudio measurement plug-in development topic.
---

# Measurement Plug-In SDK Skill

When this skill is triggered, read the full reference file before generating any code or guidance:

**Reference file**: `C:\Users\eshorman\OneDrive - Emerson\Documents\Nigel\CLI-Developer\ni_python_instruments\measurement_plugin_sdk.md`

That file contains the complete, verified patterns for:

- Full file anatomy (all required files and their roles)
- `measurement.py` structure (MeasurementService, decorators, measure function, click main)
- All `DataType` values and when to use them
- Non-streaming vs. streaming (generator) measurement patterns
- Cancellation with `threading.Event` and `grpc.StatusCode.CANCELLED`
- `.serviceconfig` JSON format and all required fields
- `.measui` XML format — every control type with exact attribute names
- `.measproj` XML format
- `pyproject.toml` and `poetry.toml` templates
- `_helpers.py` standard helpers
- `start.bat` / `install.bat` scripts
- Running locally and static registration in `C:\ProgramData\...`
- Pin map integration and `reserve_sessions` / `initialize_*` patterns
- 10 common mistakes and how to avoid them
- SDK version compatibility table
- Step-by-step quick-start checklist

Always read the reference file first — do not generate plug-in code from memory alone.
