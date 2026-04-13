"""A default measurement with an array in and out."""

import logging
import pathlib
import sys

import click
import ni_measurement_plugin_sdk_service as nims

script_or_exe = sys.executable if getattr(sys, "frozen", False) else __file__
service_directory = pathlib.Path(script_or_exe).resolve().parent
measurement_service = nims.MeasurementService(
    service_config_path=service_directory / "FirstPlugin.serviceconfig",
    ui_file_paths=[service_directory / "FirstPlugin.measui"],
)


@measurement_service.register_measurement
@measurement_service.configuration("Array in", nims.DataType.DoubleArray1D, [0.0])
@measurement_service.configuration("Text input", nims.DataType.String, "")
@measurement_service.output("Array out", nims.DataType.DoubleArray1D)
@measurement_service.output("Char count", nims.DataType.Int32)
def measure(array_input, text_input):
    """Multiply each input value by 2 and count characters in text input."""
    array_output = [x * 2 for x in array_input]
    char_count = len(text_input)
    return (array_output, char_count)


@click.command
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Enable verbose logging. Repeat to increase verbosity.",
)
def main(verbose: int) -> None:
    """Host the FirstPlugin service."""
    if verbose > 1:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=level)

    with measurement_service.host_service():
        input("Press enter to close the measurement service.\n")


if __name__ == "__main__":
    main()
