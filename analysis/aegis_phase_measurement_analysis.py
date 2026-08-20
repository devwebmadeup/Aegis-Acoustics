"""Conservative analysis of one Aegis relative-phase measurement run.

The input is a strict CSV containing one electrical-drive-output run at one
frequency, one measured sound speed, and one target.  Predicted drive phases come from
``simulation.aegis_phase_calibration.calculate_focus_solution``.  The analysis
removes one common circular phase offset and reports the remaining per-channel
relative-phase error.

Removing that offset deliberately makes this a *relative-phase-only* check.  A
passing report does not establish absolute phase/timing, acoustic pressure,
focal intensity, particle control, or end-to-end device performance.
Target-microphone and acoustic-arrival phases are a different comparison
domain and are rejected; they require a separate propagation-aware analysis.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Sequence

import numpy as np


# Direct execution (``python analysis/...py``) puts ``analysis`` rather than
# the repository root on sys.path.  Keep the normal import path first, then add
# only this file's repository root for the documented direct-CLI invocation.
try:
    from simulation.aegis_phase_calibration import (
        TAU,
        calculate_focus_solution,
        wrap_phase_rad,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by CLI tests
    if exc.name not in {"simulation", "simulation.aegis_phase_calibration"}:
        raise
    _REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_REPOSITORY_ROOT))
    from simulation.aegis_phase_calibration import (
        TAU,
        calculate_focus_solution,
        wrap_phase_rad,
    )


EXPECTED_CHANNEL_COUNT = 256
EXPECTED_CHANNEL_IDS = frozenset(range(EXPECTED_CHANNEL_COUNT))
EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_GATE_FAILED = 3
MIN_CIRCULAR_RESULTANT_LENGTH = 1e-12
MEASUREMENT_PLANE = "electrical_drive_output"
PHASE_CONVENTION = "cos_omega_t_plus_phi"
PROJECT_GATE_P95_CAP_DEG = 1.0
PROJECT_GATE_MAX_CAP_DEG = 1.0

REQUIRED_COLUMNS = (
    "provenance",
    "protocol_id",
    "device_id",
    "run_id",
    "instrument_id",
    "calibration_record_id",
    "measurement_plane",
    "phase_reference_id",
    "phase_convention",
    "channel_id",
    "emitter_x_m",
    "emitter_y_m",
    "emitter_z_m",
    "frequency_hz",
    "sound_speed_m_s",
    "target_x_m",
    "target_y_m",
    "target_z_m",
    "measured_drive_phase_rad",
)

_CONDITION_TEXT_COLUMNS = (
    "provenance",
    "protocol_id",
    "device_id",
    "run_id",
    "instrument_id",
    "calibration_record_id",
    "measurement_plane",
    "phase_reference_id",
    "phase_convention",
)
_CONDITION_FLOAT_COLUMNS = (
    "frequency_hz",
    "sound_speed_m_s",
    "target_x_m",
    "target_y_m",
    "target_z_m",
)


class MeasurementDataError(ValueError):
    """Raised when a measurement CSV violates the declared run schema."""


@dataclass(frozen=True)
class PhaseMeasurement:
    """One measured electrical-drive channel in SI/radian units."""

    channel_id: int
    emitter_m: tuple[float, float, float]
    measured_drive_phase_rad: float


@dataclass(frozen=True)
class PhaseMeasurementRun:
    """Validated data for exactly one acquisition condition."""

    provenance: str
    protocol_id: str
    device_id: str
    run_id: str
    instrument_id: str
    calibration_record_id: str
    measurement_plane: str
    phase_reference_id: str
    phase_convention: str
    frequency_hz: float
    sound_speed_m_s: float
    target_m: tuple[float, float, float]
    measurements: tuple[PhaseMeasurement, ...]


@dataclass(frozen=True)
class LoadedMeasurementCsv:
    """One immutable parse result bound to the exact bytes that were hashed."""

    run: PhaseMeasurementRun
    sha256: str
    byte_count: int


def _validate_measurement_run_object(run: PhaseMeasurementRun) -> None:
    """Apply CSV-equivalent invariants to callers using the Python API."""

    if not isinstance(run.provenance, str) or run.provenance not in {
        "synthetic",
        "experimental",
    }:
        raise MeasurementDataError(
            "run provenance must be exactly 'synthetic' or 'experimental'"
        )
    for name, value in (
        ("protocol_id", run.protocol_id),
        ("device_id", run.device_id),
        ("run_id", run.run_id),
        ("instrument_id", run.instrument_id),
        ("calibration_record_id", run.calibration_record_id),
        ("phase_reference_id", run.phase_reference_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise MeasurementDataError(f"run {name} must be a non-empty string")
    if run.measurement_plane != MEASUREMENT_PLANE:
        candidate = str(run.measurement_plane).lower()
        if any(token in candidate for token in ("microphone", "acoustic", "arrival")):
            raise MeasurementDataError(
                "target-microphone/acoustic-arrival phase data are unsupported by "
                "this electrical-drive analyzer and require a separate analysis"
            )
        raise MeasurementDataError(
            f"run measurement_plane must be exactly {MEASUREMENT_PLANE!r}"
        )
    if run.phase_convention != PHASE_CONVENTION:
        raise MeasurementDataError(
            f"run phase_convention must be exactly {PHASE_CONVENTION!r}"
        )
    for name, value in (
        ("frequency_hz", run.frequency_hz),
        ("sound_speed_m_s", run.sound_speed_m_s),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MeasurementDataError(f"run {name} must be finite and positive")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MeasurementDataError(
                f"run {name} must be finite and positive"
            ) from exc
        if not math.isfinite(numeric_value) or numeric_value <= 0.0:
            raise MeasurementDataError(f"run {name} must be finite and positive")

    try:
        target = tuple(run.target_m)
    except (TypeError, ValueError) as exc:
        raise MeasurementDataError(
            "run target_m must contain three finite values"
        ) from exc
    if len(target) != 3:
        raise MeasurementDataError("run target_m must contain three finite values")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in target
    ):
        raise MeasurementDataError("run target_m must contain three finite values")
    try:
        target_numeric = tuple(float(value) for value in target)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MeasurementDataError(
            "run target_m must contain three finite values"
        ) from exc
    if any(isinstance(value, bool) for value in target) or any(
        not math.isfinite(value) for value in target_numeric
    ):
        raise MeasurementDataError("run target_m must contain three finite values")

    if not isinstance(run.measurements, tuple) or not run.measurements:
        raise MeasurementDataError("run must contain at least one measurement")

    channel_ids: set[int] = set()
    emitter_coordinates: set[tuple[float, float, float]] = set()
    for item in run.measurements:
        if not isinstance(item, PhaseMeasurement):
            raise MeasurementDataError(
                "run measurements must contain only PhaseMeasurement values"
            )
        if (
            isinstance(item.channel_id, bool)
            or not isinstance(item.channel_id, int)
            or item.channel_id not in EXPECTED_CHANNEL_IDS
        ):
            raise MeasurementDataError("channel_id must be an integer from 0 to 255")
        if item.channel_id in channel_ids:
            raise MeasurementDataError(f"duplicate channel_id {item.channel_id!r}")
        channel_ids.add(item.channel_id)

        try:
            emitter = tuple(item.emitter_m)
        except (TypeError, ValueError) as exc:
            raise MeasurementDataError(
                f"channel {item.channel_id}: emitter_m must contain three finite values"
            ) from exc
        if len(emitter) != 3:
            raise MeasurementDataError(
                f"channel {item.channel_id}: emitter_m must contain three finite values"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in emitter
        ):
            raise MeasurementDataError(
                f"channel {item.channel_id}: emitter_m must contain three finite values"
            )
        try:
            coordinate = tuple(float(value) for value in emitter)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MeasurementDataError(
                f"channel {item.channel_id}: emitter_m must contain three finite values"
            ) from exc
        if any(isinstance(value, bool) for value in emitter) or any(
            not math.isfinite(value) for value in coordinate
        ):
            raise MeasurementDataError(
                f"channel {item.channel_id}: emitter_m must contain three finite values"
            )
        if coordinate in emitter_coordinates:
            raise MeasurementDataError(f"duplicate emitter coordinates {coordinate!r}")
        emitter_coordinates.add(coordinate)
        if isinstance(item.measured_drive_phase_rad, bool) or not isinstance(
            item.measured_drive_phase_rad, (int, float)
        ):
            raise MeasurementDataError(
                f"channel {item.channel_id}: measured_drive_phase_rad must be finite"
            )
        try:
            measured_phase = float(item.measured_drive_phase_rad)
        except (TypeError, ValueError, OverflowError) as exc:
            raise MeasurementDataError(
                f"channel {item.channel_id}: measured_drive_phase_rad must be finite"
            ) from exc
        if not math.isfinite(measured_phase):
            raise MeasurementDataError(
                f"channel {item.channel_id}: measured_drive_phase_rad must be finite"
            )


def _required_text(value: object, column: str, line_number: int) -> str:
    if value is None:
        raise MeasurementDataError(
            f"line {line_number}: missing value for {column!r}"
        )
    result = str(value).strip()
    if not result:
        raise MeasurementDataError(
            f"line {line_number}: {column!r} must be non-empty"
        )
    return result


def _finite_float(value: object, column: str, line_number: int) -> float:
    text = _required_text(value, column, line_number)
    try:
        result = float(text)
    except ValueError as exc:
        raise MeasurementDataError(
            f"line {line_number}: {column!r} must be a number"
        ) from exc
    if not math.isfinite(result):
        raise MeasurementDataError(
            f"line {line_number}: {column!r} must be finite"
        )
    return result


def _positive_float(value: object, column: str, line_number: int) -> float:
    result = _finite_float(value, column, line_number)
    if result <= 0.0:
        raise MeasurementDataError(
            f"line {line_number}: {column!r} must be greater than zero"
        )
    return result


def _parse_measurement_csv_bytes(csv_bytes: bytes) -> PhaseMeasurementRun:
    """Parse the strict single-run schema from an immutable byte snapshot.

    Headers must match :data:`REQUIRED_COLUMNS` exactly (order is irrelevant).
    Every row must repeat the same provenance, identifiers, frequency, measured
    sound speed, target, measurement plane, reference, and convention.  Channel
    identifiers must be unique.  The loader accepts any finite measured drive
    phase and the analysis wraps it circularly.
    Coverage of all 256 channels is evaluated by the evidence gate rather than
    treated as a parse error, so incomplete diagnostic runs still get reports.
    """

    if not isinstance(csv_bytes, bytes):
        raise MeasurementDataError("csv_bytes must be a bytes object")
    try:
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MeasurementDataError("input CSV must be valid UTF-8") from exc

    with io.StringIO(csv_text, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise MeasurementDataError("CSV must contain a header row")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise MeasurementDataError("CSV header contains duplicate column names")

        present = set(reader.fieldnames)
        required = set(REQUIRED_COLUMNS)
        missing = sorted(required - present)
        unexpected = sorted(present - required)
        if missing or unexpected:
            unsupported_domain_columns = sorted(
                column
                for column in unexpected
                if any(
                    token in column.lower()
                    for token in ("microphone", "acoustic", "arrival")
                )
            )
            if unsupported_domain_columns:
                raise MeasurementDataError(
                    "target-microphone/acoustic-arrival columns are unsupported "
                    "by this electrical-drive analyzer and require a separate analysis: "
                    + ", ".join(unsupported_domain_columns)
                )
            details = []
            if missing:
                details.append("missing columns: " + ", ".join(missing))
            if unexpected:
                details.append("unexpected columns: " + ", ".join(unexpected))
            raise MeasurementDataError("invalid CSV schema; " + "; ".join(details))

        condition: dict[str, str | float] | None = None
        measurements: list[PhaseMeasurement] = []
        seen_channel_ids: set[int] = set()
        seen_emitter_coordinates: set[tuple[float, float, float]] = set()

        for raw_row in reader:
            line_number = reader.line_num
            if None in raw_row:
                raise MeasurementDataError(
                    f"line {line_number}: row has more fields than the header"
                )

            row_condition: dict[str, str | float] = {
                column: _required_text(raw_row[column], column, line_number)
                for column in _CONDITION_TEXT_COLUMNS
            }
            provenance = str(row_condition["provenance"])
            if provenance not in {"synthetic", "experimental"}:
                raise MeasurementDataError(
                    f"line {line_number}: provenance must be exactly "
                    "'synthetic' or 'experimental'"
                )
            measurement_plane = str(row_condition["measurement_plane"])
            if measurement_plane != MEASUREMENT_PLANE:
                candidate = measurement_plane.lower()
                if any(
                    token in candidate
                    for token in ("microphone", "acoustic", "arrival")
                ):
                    raise MeasurementDataError(
                        f"line {line_number}: target-microphone/acoustic-arrival "
                        "phase data are unsupported by this electrical-drive "
                        "analyzer and require a separate analysis"
                    )
                raise MeasurementDataError(
                    f"line {line_number}: measurement_plane must be exactly "
                    f"{MEASUREMENT_PLANE!r}"
                )
            if row_condition["phase_convention"] != PHASE_CONVENTION:
                raise MeasurementDataError(
                    f"line {line_number}: phase_convention must be exactly "
                    f"{PHASE_CONVENTION!r}"
                )

            row_condition["frequency_hz"] = _positive_float(
                raw_row["frequency_hz"], "frequency_hz", line_number
            )
            row_condition["sound_speed_m_s"] = _positive_float(
                raw_row["sound_speed_m_s"], "sound_speed_m_s", line_number
            )
            for column in ("target_x_m", "target_y_m", "target_z_m"):
                row_condition[column] = _finite_float(
                    raw_row[column], column, line_number
                )

            if condition is None:
                condition = row_condition
            else:
                for column in (*_CONDITION_TEXT_COLUMNS, *_CONDITION_FLOAT_COLUMNS):
                    if row_condition[column] != condition[column]:
                        raise MeasurementDataError(
                            f"line {line_number}: {column!r} differs within one CSV; "
                            "one file must contain exactly one run and condition"
                        )

            channel_id_text = _required_text(
                raw_row["channel_id"], "channel_id", line_number
            )
            try:
                channel_id = int(channel_id_text)
            except ValueError as exc:
                raise MeasurementDataError(
                    f"line {line_number}: channel_id must be an integer from 0 to 255"
                ) from exc
            if channel_id_text != str(channel_id) or channel_id not in EXPECTED_CHANNEL_IDS:
                raise MeasurementDataError(
                    f"line {line_number}: channel_id must use the canonical integer "
                    "form 0 through 255"
                )
            if channel_id in seen_channel_ids:
                raise MeasurementDataError(
                    f"line {line_number}: duplicate channel_id {channel_id!r}"
                )
            seen_channel_ids.add(channel_id)

            emitter_m = tuple(
                _finite_float(raw_row[column], column, line_number)
                for column in ("emitter_x_m", "emitter_y_m", "emitter_z_m")
            )
            if emitter_m in seen_emitter_coordinates:
                raise MeasurementDataError(
                    f"line {line_number}: duplicate emitter coordinates {emitter_m!r}"
                )
            seen_emitter_coordinates.add(emitter_m)
            measured_drive_phase_rad = _finite_float(
                raw_row["measured_drive_phase_rad"],
                "measured_drive_phase_rad",
                line_number,
            )
            measurements.append(
                PhaseMeasurement(
                    channel_id=channel_id,
                    emitter_m=emitter_m,
                    measured_drive_phase_rad=measured_drive_phase_rad,
                )
            )

    if condition is None or not measurements:
        raise MeasurementDataError("CSV must contain at least one measurement row")

    return PhaseMeasurementRun(
        provenance=str(condition["provenance"]),
        protocol_id=str(condition["protocol_id"]),
        device_id=str(condition["device_id"]),
        run_id=str(condition["run_id"]),
        instrument_id=str(condition["instrument_id"]),
        calibration_record_id=str(condition["calibration_record_id"]),
        measurement_plane=str(condition["measurement_plane"]),
        phase_reference_id=str(condition["phase_reference_id"]),
        phase_convention=str(condition["phase_convention"]),
        frequency_hz=float(condition["frequency_hz"]),
        sound_speed_m_s=float(condition["sound_speed_m_s"]),
        target_m=(
            float(condition["target_x_m"]),
            float(condition["target_y_m"]),
            float(condition["target_z_m"]),
        ),
        measurements=tuple(measurements),
    )


def load_measurement_csv_snapshot(
    path: str | os.PathLike[str],
) -> LoadedMeasurementCsv:
    """Read once, then bind parsing and SHA-256 to those exact CSV bytes."""

    input_path = Path(path)
    try:
        csv_bytes = input_path.read_bytes()
    except OSError as exc:
        raise MeasurementDataError(f"cannot read input CSV {input_path}: {exc}") from exc
    run = _parse_measurement_csv_bytes(csv_bytes)
    return LoadedMeasurementCsv(
        run=run,
        sha256=hashlib.sha256(csv_bytes).hexdigest(),
        byte_count=len(csv_bytes),
    )


def load_measurement_csv(path: str | os.PathLike[str]) -> PhaseMeasurementRun:
    """Load a validated run from one read of the input CSV."""

    return load_measurement_csv_snapshot(path).run


def signed_circular_difference_rad(angle_rad, reference_rad):
    """Return ``angle-reference`` wrapped to the interval ``[-pi, pi)``."""

    angle = np.asarray(angle_rad, dtype=float)
    reference = np.asarray(reference_rad, dtype=float)
    if np.any(~np.isfinite(angle)) or np.any(~np.isfinite(reference)):
        raise ValueError("circular angles must be finite")
    result = (angle - reference + np.pi) % TAU - np.pi
    if np.ndim(result) == 0:
        return float(result)
    return result


def _threshold_deg(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementDataError(f"{name} must be a real number or None")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MeasurementDataError(
            f"{name} must be a finite real number or None"
        ) from exc
    if not math.isfinite(result) or not 0.0 < result < 180.0:
        raise MeasurementDataError(
            f"{name} must be finite and in the interval (0, 180); "
            "180 degrees is a vacuous circular-error threshold"
        )
    return result


def _metric_set(values_rad: np.ndarray) -> dict[str, float]:
    absolute = np.abs(values_rad)
    return {
        "p50": float(np.percentile(absolute, 50.0, method="linear")),
        "p95": float(np.percentile(absolute, 95.0, method="linear")),
        "p99": float(np.percentile(absolute, 99.0, method="linear")),
        "max": float(np.max(absolute)),
        "rms": float(np.sqrt(np.mean(np.square(values_rad)))),
    }


def analyze_measurement_run(
    run: PhaseMeasurementRun,
    *,
    p95_threshold_deg: float | None = None,
    max_threshold_deg: float | None = None,
    instrument_calibrated: bool = False,
    thresholds_prespecified: bool = False,
) -> dict[str, object]:
    """Analyze one run and evaluate the deliberately narrow evidence gate.

    Experimental data can pass only when both degree thresholds are supplied
    *and* the caller separately self-attests that those values were fixed before
    examining this run.  Passing additionally requires an affirmative
    calibrated-instrument self-attestation and exactly 256 unique channels.
    Synthetic provenance is demonstration-only and can never pass.
    """

    if not isinstance(run, PhaseMeasurementRun):
        raise MeasurementDataError("run must be a PhaseMeasurementRun")
    _validate_measurement_run_object(run)
    if not isinstance(instrument_calibrated, bool):
        raise MeasurementDataError("instrument_calibrated must be a bool")
    if not isinstance(thresholds_prespecified, bool):
        raise MeasurementDataError("thresholds_prespecified must be a bool")
    p95_threshold_deg = _threshold_deg(
        p95_threshold_deg, "p95_threshold_deg"
    )
    max_threshold_deg = _threshold_deg(max_threshold_deg, "max_threshold_deg")

    coordinates = tuple(item.emitter_m for item in run.measurements)
    try:
        focus = calculate_focus_solution(
            coordinates,
            run.target_m,
            run.sound_speed_m_s,
            run.frequency_hz,
        )
    except (TypeError, ValueError) as exc:
        raise MeasurementDataError(
            f"measurement geometry cannot produce a focus prediction: {exc}"
        ) from exc

    predicted_rad = np.asarray(focus.phase_rad, dtype=float)
    measured_rad = np.asarray(
        [item.measured_drive_phase_rad for item in run.measurements], dtype=float
    )
    raw_difference_rad = signed_circular_difference_rad(
        measured_rad, predicted_rad
    )

    mean_sine = float(np.mean(np.sin(raw_difference_rad)))
    mean_cosine = float(np.mean(np.cos(raw_difference_rad)))
    resultant_length = math.hypot(mean_sine, mean_cosine)
    if resultant_length <= MIN_CIRCULAR_RESULTANT_LENGTH:
        raise MeasurementDataError(
            "the common circular offset is undefined because the phase-"
            "difference resultant is effectively zero"
        )
    global_offset_rad = math.atan2(mean_sine, mean_cosine)
    residual_rad = signed_circular_difference_rad(
        raw_difference_rad, global_offset_rad
    )

    metrics_rad = _metric_set(residual_rad)
    radians_to_degrees = 180.0 / math.pi
    metrics_deg = {
        key: float(value * radians_to_degrees)
        for key, value in metrics_rad.items()
    }

    threshold_values_supplied = (
        p95_threshold_deg is not None and max_threshold_deg is not None
    )
    p95_threshold_within_project_cap = bool(
        p95_threshold_deg is not None
        and p95_threshold_deg <= PROJECT_GATE_P95_CAP_DEG
    )
    max_threshold_within_project_cap = bool(
        max_threshold_deg is not None
        and max_threshold_deg <= PROJECT_GATE_MAX_CAP_DEG
    )
    thresholds_within_project_caps = bool(
        threshold_values_supplied
        and p95_threshold_within_project_cap
        and max_threshold_within_project_cap
    )
    observed_channel_ids = {item.channel_id for item in run.measurements}
    expected_coverage = observed_channel_ids == EXPECTED_CHANNEL_IDS
    p95_within_threshold = bool(
        threshold_values_supplied
        and metrics_deg["p95"] <= float(p95_threshold_deg)
    )
    max_within_threshold = bool(
        threshold_values_supplied
        and metrics_deg["max"] <= float(max_threshold_deg)
    )
    experimental = run.provenance == "experimental"
    passed = bool(
        experimental
        and threshold_values_supplied
        and thresholds_within_project_caps
        and thresholds_prespecified
        and instrument_calibrated
        and expected_coverage
        and p95_within_threshold
        and max_within_threshold
    )

    reasons: list[str] = []
    if not experimental:
        reasons.append(
            "synthetic provenance is demonstration-only and cannot validate a device"
        )
    if not expected_coverage:
        reasons.append(
            f"expected {EXPECTED_CHANNEL_COUNT} unique channels, observed "
            f"{len(run.measurements)}"
        )
    if experimental and not threshold_values_supplied:
        reasons.append(
            "both p95 and maximum residual threshold values must be supplied"
        )
    if experimental and not thresholds_prespecified:
        reasons.append(
            "caller did not self-attest that thresholds were fixed before examining this run"
        )
    if experimental and p95_threshold_deg is not None and not p95_threshold_within_project_cap:
        reasons.append(
            f"supplied p95 threshold exceeds the temporary project cap of "
            f"{PROJECT_GATE_P95_CAP_DEG:g} degree"
        )
    if experimental and max_threshold_deg is not None and not max_threshold_within_project_cap:
        reasons.append(
            f"supplied maximum threshold exceeds the temporary project cap of "
            f"{PROJECT_GATE_MAX_CAP_DEG:g} degree"
        )
    if experimental and not instrument_calibrated:
        reasons.append(
            "calibrated-instrument self-attestation was not supplied"
        )
    if experimental and threshold_values_supplied and not p95_within_threshold:
        reasons.append("p95 absolute residual exceeds its predeclared threshold")
    if experimental and threshold_values_supplied and not max_within_threshold:
        reasons.append("maximum absolute residual exceeds its predeclared threshold")

    channels = []
    for index, item in enumerate(run.measurements):
        channels.append(
            {
                "channel_id": item.channel_id,
                "emitter_m": list(item.emitter_m),
                "measured_drive_phase_rad": item.measured_drive_phase_rad,
                "measured_drive_phase_wrapped_rad": wrap_phase_rad(
                    item.measured_drive_phase_rad
                ),
                "predicted_drive_phase_wrapped_rad": float(predicted_rad[index]),
                "raw_measured_drive_minus_predicted_drive_rad": float(
                    raw_difference_rad[index]
                ),
                "relative_phase_residual_rad": float(residual_rad[index]),
                "absolute_relative_phase_residual_rad": float(
                    abs(residual_rad[index])
                ),
            }
        )

    return {
        "schema_version": "aegis.phase-measurement-report.v2",
        "analysis_scope": "relative_phase_only_after_global_circular_offset_removal",
        "provenance": run.provenance,
        "protocol_id": run.protocol_id,
        "device_id": run.device_id,
        "run_id": run.run_id,
        "traceability": {
            "instrument_id": run.instrument_id,
            "calibration_record_id": run.calibration_record_id,
            "phase_reference_id": run.phase_reference_id,
            "identifiers_present": True,
            "identifiers_verified_by_this_tool": False,
        },
        "comparison": {
            "domain": MEASUREMENT_PLANE,
            "measurement_plane": run.measurement_plane,
            "phase_convention": run.phase_convention,
            "measured_quantity": "measured_drive_phase_rad",
            "predicted_quantity": "wrapped_electrical_drive_phase_rad",
            "phase_reference_id": run.phase_reference_id,
            "target_microphone_or_acoustic_arrival_supported": False,
            "target_microphone_or_acoustic_arrival_requirement": (
                "separate measurement schema and propagation/arrival analysis"
            ),
        },
        "conditions": {
            "frequency_hz": run.frequency_hz,
            "sound_speed_m_s": run.sound_speed_m_s,
            "target_m": list(run.target_m),
        },
        "coverage": {
            "expected_unique_channels": EXPECTED_CHANNEL_COUNT,
            "observed_unique_channels": len(run.measurements),
            "expected_channel_id_range": [0, EXPECTED_CHANNEL_COUNT - 1],
            "exact_id_set_0_through_255": expected_coverage,
            "complete": expected_coverage,
        },
        "global_circular_offset": {
            "rad": global_offset_rad,
            "wrapped_rad": wrap_phase_rad(global_offset_rad),
            "deg": global_offset_rad * radians_to_degrees,
            "resultant_length": resultant_length,
            "minimum_accepted_resultant_length": MIN_CIRCULAR_RESULTANT_LENGTH,
            "method": "circular_mean_of_wrapped_measured_minus_predicted",
            "fitted_degrees_of_freedom": 1,
        },
        "residual_metrics": {
            "definition": "absolute residual for percentiles/max; signed residual for RMS",
            "rad": metrics_rad,
            "deg": metrics_deg,
        },
        "gate": {
            "name": "single_run_256_channel_relative_phase_gate",
            "passed": passed,
            "dataset_rule_passed": passed,
            "passed_field_meaning": (
                "this one run satisfied the declared relative electrical-drive "
                "phase rule; it is not device-performance validation"
            ),
            "expected_channel_count": EXPECTED_CHANNEL_COUNT,
            "threshold_values_supplied": threshold_values_supplied,
            "thresholds_prespecified_self_attested": thresholds_prespecified,
            "instrument_calibrated_self_attested": instrument_calibrated,
            "thresholds_deg": {
                "p95": p95_threshold_deg,
                "max": max_threshold_deg,
            },
            "temporary_project_threshold_caps_deg": {
                "p95": PROJECT_GATE_P95_CAP_DEG,
                "max": PROJECT_GATE_MAX_CAP_DEG,
                "rule_kind": "temporary_engineering_rule",
                "is_device_validation": False,
            },
            "checks": {
                "experimental_provenance": experimental,
                "unique_256_channel_coverage": expected_coverage,
                "traceability_identifiers_present": True,
                "p95_threshold_within_project_cap": (
                    p95_threshold_within_project_cap
                ),
                "max_threshold_within_project_cap": (
                    max_threshold_within_project_cap
                ),
                "thresholds_within_project_caps": thresholds_within_project_caps,
                "p95_within_threshold": p95_within_threshold,
                "max_within_threshold": max_within_threshold,
            },
            "failure_reasons": reasons,
        },
        # These top-level flags make it difficult for downstream consumers to
        # accidentally promote synthetic output into device evidence.
        "demonstration_only": not experimental,
        "passed": passed,
        "passed_field_meaning": (
            "backward-compatible alias for "
            "single_run_relative_drive_phase_rule_passed"
        ),
        "experimental_data_supplied": experimental,
        "experimental_label_authenticated": False,
        "single_run_relative_drive_phase_rule_passed": passed,
        "device_relative_phase_gate_passed": passed,
        "device_relative_phase_gate_passed_is_deprecated_alias": True,
        "device_performance_validated": False,
        "channels": channels,
        "limitations": [
            "One fitted global circular phase offset is removed; absolute phase and absolute timing are not tested.",
            "The global-offset fit consumes one degree of freedom before residual metrics are computed.",
            "A passing experimental gate is evidence only for relative channel phase in this one run and declared condition.",
            "Emitter coordinates, target coordinates, and measured sound speed are treated as inputs and are not independently verified here.",
            "The calibrated-instrument flag is a caller self-attestation, not a calibration certificate or traceability audit.",
            "The prespecified-threshold flag is a caller self-attestation; this tool cannot verify when the thresholds were chosen or whether results were previously inspected.",
            "The 1.0-degree p95 and maximum threshold caps are temporary project engineering rules, not universal acceptance limits or device validation.",
            "Only electrical-drive-output phases using cos(omega*t+phi) are compared; target-microphone and acoustic-arrival phases require a separate propagation-aware analysis.",
            "Instrument, calibration-record, and phase-reference identifiers are required for traceability but are not authenticated by this tool.",
            "Amplitude balance, acoustic pressure, 3-D focal shape, sidelobes, streaming, thermal drift, and transducer settling are not measured.",
            "Repeatability, reproducibility, uncertainty, environmental sweeps, particle behavior, and wafer outcomes require separate experiments.",
        ],
    }


def analyze_measurement_csv(
    path: str | os.PathLike[str],
    *,
    p95_threshold_deg: float | None = None,
    max_threshold_deg: float | None = None,
    instrument_calibrated: bool = False,
    thresholds_prespecified: bool = False,
) -> dict[str, object]:
    """Load, analyze, and attach immutable input-file provenance."""

    input_path = Path(path)
    snapshot = load_measurement_csv_snapshot(input_path)
    report = analyze_measurement_run(
        snapshot.run,
        p95_threshold_deg=p95_threshold_deg,
        max_threshold_deg=max_threshold_deg,
        instrument_calibrated=instrument_calibrated,
        thresholds_prespecified=thresholds_prespecified,
    )
    report["input"] = {
        "path": str(input_path),
        "sha256": snapshot.sha256,
        "byte_count": snapshot.byte_count,
        "hash_binding": "sha256_of_exact_bytes_parsed",
        "required_columns": list(REQUIRED_COLUMNS),
    }
    return report


def _positive_threshold_argument(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a numeric degree threshold") from exc
    if not math.isfinite(value) or not 0.0 < value < 180.0:
        raise argparse.ArgumentTypeError(
            "threshold must be in (0, 180) degrees; 180 is vacuous"
        )
    return value


def _same_file(input_path: Path, output_path: Path) -> bool:
    if input_path.resolve(strict=False) == output_path.resolve(strict=False):
        return True
    try:
        return input_path.exists() and output_path.exists() and os.path.samefile(
            input_path, output_path
        )
    except OSError:
        return False


def atomic_write_json(path: str | os.PathLike[str], document: object) -> None:
    """Atomically replace a JSON report in its destination directory."""

    output_path = Path(path)
    parent = output_path.parent
    if not parent.is_dir():
        raise OSError(f"output directory does not exist: {parent}")

    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(document, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output_path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def summary_without_channel_details(report: dict[str, object]) -> dict[str, object]:
    """Return a shallow report copy with only the per-channel array omitted."""

    if not isinstance(report, dict):
        raise MeasurementDataError("report must be a dictionary")
    channels = report.get("channels")
    if not isinstance(channels, list):
        raise MeasurementDataError("report does not contain a channel-details list")
    summary = dict(report)
    summary.pop("channels")
    summary["channel_details_included"] = False
    summary["channel_details_count"] = len(channels)
    return summary


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one strict phase-measurement CSV. The result is a "
            "relative-phase-only gate after removing one global circular offset."
        )
    )
    parser.add_argument("input_csv", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON report path; written with atomic replacement",
    )
    parser.add_argument(
        "--p95-threshold-deg",
        "--p95-limit-deg",
        dest="p95_threshold_deg",
        type=_positive_threshold_argument,
        help=(
            "predeclared p95 absolute residual limit in degrees; values above "
            "the temporary 1-degree project cap are diagnostic-only"
        ),
    )
    parser.add_argument(
        "--max-threshold-deg",
        "--max-limit-deg",
        dest="max_threshold_deg",
        type=_positive_threshold_argument,
        help=(
            "predeclared maximum absolute residual limit in degrees; values "
            "above the temporary 1-degree project cap are diagnostic-only"
        ),
    )
    parser.add_argument(
        "--confirm-prespecified-thresholds",
        dest="thresholds_prespecified",
        action="store_true",
        help=(
            "self-attest that both threshold values were fixed before any "
            "inspection of this run's results"
        ),
    )
    parser.add_argument(
        "--instrument-calibrated",
        "--attest-calibrated-instrument",
        dest="instrument_calibrated",
        action="store_true",
        help=(
            "self-attest that the phase measurement instrument had a current "
            "calibration before this run"
        ),
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help=(
            "omit the 256-element channels array from JSON while retaining its count"
        ),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="return zero after a valid analysis even when the evidence gate fails",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        if args.output is not None and _same_file(args.input_csv, args.output):
            raise MeasurementDataError(
                "refusing to overwrite the input CSV with the JSON output"
            )

        report = analyze_measurement_csv(
            args.input_csv,
            p95_threshold_deg=args.p95_threshold_deg,
            max_threshold_deg=args.max_threshold_deg,
            instrument_calibrated=args.instrument_calibrated,
            thresholds_prespecified=args.thresholds_prespecified,
        )
        if args.summary_only:
            report = summary_without_channel_details(report)
        if args.output is not None:
            atomic_write_json(args.output, report)
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        if args.report_only or report["passed"]:
            return EXIT_OK
        return EXIT_GATE_FAILED
    except (MeasurementDataError, OSError, csv.Error, TypeError, ValueError) as exc:
        error = {
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        }
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
