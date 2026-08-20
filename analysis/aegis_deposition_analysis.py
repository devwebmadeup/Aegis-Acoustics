#!/usr/bin/env python3
"""Analyze randomized paired particle-deposition trials.

Each CSV row is one experimental block containing a field-OFF and field-ON
measurement made under matched conditions.  The primary effect is the pairwise
natural-log ratio ``log(ON / OFF)``.  Aggregation on the log scale yields a
geometric-mean deposition ratio and reduction.

This module intentionally does not add pseudocounts.  Zero raw counts, or
non-positive counts after blank subtraction, cannot be log-transformed and are
rejected.  Any detection-limit treatment must be specified in the experimental
protocol before outcomes are inspected.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import numpy as np

if __package__:
    from . import aegis_deposition_power as deposition_power
else:  # Support ``python analysis/aegis_deposition_analysis.py ...``.
    import aegis_deposition_power as deposition_power


DEFAULT_MINIMUM_REDUCTION_FRACTION = 0.30
DEFAULT_MINIMUM_INDEPENDENT_RUNS = 6
DEFAULT_MINIMUM_RUNS_PER_ORDER = 2
DEFAULT_MINIMUM_ORDER_BALANCE_RATIO = 0.50
DEFAULT_MAX_ORDER_RATIO_FOLD_DIFFERENCE = 1.50
DEFAULT_MAX_TEMPERATURE_SPAN_C = 1.0
DEFAULT_MAX_RELATIVE_HUMIDITY_SPAN_PCT = 5.0
DEFAULT_BOOTSTRAP_RESAMPLES = 10_000
DEFAULT_BOOTSTRAP_SEED = 20_260_820
MINIMUM_BOOTSTRAP_RESAMPLES = 10_000
MINIMUM_GATE_BOOTSTRAP_RESAMPLES = 10_000
MAXIMUM_BOOTSTRAP_RESAMPLES = 1_000_000
MONTE_CARLO_GUARD_Z = 1.96

BLANK_POLICY_NONE = "none"
BLANK_POLICY_PAIRED_SUBTRACT = "paired_subtract"
BLANK_POLICIES = (BLANK_POLICY_NONE, BLANK_POLICY_PAIRED_SUBTRACT)

RANDOMIZED_ORDERS = ("off_then_on", "on_then_off")
DATA_PROVENANCES = ("synthetic", "experimental")

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_GATE_FAILED = 3

REQUIRED_COLUMNS = (
    "block_id",
    "independent_run_id",
    "data_provenance",
    "randomized_order",
    "particle_nm",
    "gas",
    "flow_slm",
    "exposure_s",
    "field_off_count",
    "field_on_count",
)
BLANK_COLUMNS = ("field_off_blank_count", "field_on_blank_count")
TRACEABILITY_COLUMNS = (
    "device_id",
    "trial_day",
    "protocol_id",
    "aerosol_batch_id",
    "measurement_method_id",
    "exclusion_policy_id",
    "stopping_rule_id",
    "replacement_policy_id",
)


@dataclass(frozen=True)
class PairedTrial:
    """One matched field-OFF/field-ON block from the trial CSV."""

    block_id: str
    independent_run_id: str
    data_provenance: str
    randomized_order: str
    particle_nm: float
    gas: str
    flow_slm: float
    exposure_s: float
    field_off_count: float
    field_on_count: float
    field_off_blank_count: Optional[float] = None
    field_on_blank_count: Optional[float] = None
    sampled_area_cm2: Optional[float] = None
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    device_id: Optional[str] = None
    trial_day: Optional[str] = None
    protocol_id: Optional[str] = None
    aerosol_batch_id: Optional[str] = None
    measurement_method_id: Optional[str] = None
    exclusion_policy_id: Optional[str] = None
    stopping_rule_id: Optional[str] = None
    replacement_policy_id: Optional[str] = None
    notes: str = ""


def _row_name(row_number: int, column: str) -> str:
    return f"CSV row {row_number}, column '{column}'"


def _required_text(row: dict[str, Optional[str]], column: str, row_number: int) -> str:
    value = row.get(column)
    if value is None or not value.strip():
        raise ValueError(f"{_row_name(row_number, column)} is required")
    return value.strip()


def _number(
    row: dict[str, Optional[str]],
    column: str,
    row_number: int,
    *,
    minimum: Optional[float] = None,
    minimum_inclusive: bool = True,
    maximum: Optional[float] = None,
) -> float:
    raw = _required_text(row, column, row_number)
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(
            f"{_row_name(row_number, column)} must be numeric, got {raw!r}"
        ) from error
    if not math.isfinite(value):
        raise ValueError(f"{_row_name(row_number, column)} must be finite")
    if minimum is not None:
        invalid = value < minimum if minimum_inclusive else value <= minimum
        if invalid:
            comparator = ">=" if minimum_inclusive else ">"
            raise ValueError(
                f"{_row_name(row_number, column)} must be {comparator} {minimum}"
            )
    if maximum is not None and value > maximum:
        raise ValueError(
            f"{_row_name(row_number, column)} must be <= {maximum}"
        )
    return value


def _optional_number(
    row: dict[str, Optional[str]],
    column: str,
    row_number: int,
    *,
    minimum: Optional[float] = None,
    minimum_inclusive: bool = True,
    maximum: Optional[float] = None,
) -> Optional[float]:
    raw = row.get(column)
    if raw is None or not raw.strip():
        return None
    return _number(
        row,
        column,
        row_number,
        minimum=minimum,
        minimum_inclusive=minimum_inclusive,
        maximum=maximum,
    )


def _optional_text(row: dict[str, Optional[str]], column: str) -> Optional[str]:
    raw = row.get(column)
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def load_paired_trials(
    csv_path: Path | str,
    *,
    _snapshot_bytes: Optional[bytes] = None,
) -> list[PairedTrial]:
    """Load and validate paired blocks from ``csv_path``.

    Raw field counts must be strictly positive because the primary statistic is
    a log ratio.  Blank counts, when provided, may be zero but not negative.
    The two blank columns must be both present or both absent, and each row must
    supply either both blank values or neither value.
    """

    path = Path(csv_path)
    if _snapshot_bytes is None:
        csv_source = path.open("r", encoding="utf-8-sig", newline="")
    else:
        if not isinstance(_snapshot_bytes, bytes):
            raise TypeError("_snapshot_bytes must be bytes")
        csv_source = io.StringIO(
            _snapshot_bytes.decode("utf-8-sig"),
            newline="",
        )
    with csv_source as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV must contain a header row")

        fieldnames = [name.strip() for name in reader.fieldnames]
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError("CSV header contains duplicate column names")
        if fieldnames != reader.fieldnames:
            raise ValueError("CSV header names must not contain surrounding whitespace")

        missing_columns = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing_columns:
            raise ValueError(
                "CSV is missing required column(s): " + ", ".join(missing_columns)
            )

        blank_header_count = sum(name in fieldnames for name in BLANK_COLUMNS)
        if blank_header_count == 1:
            raise ValueError(
                "blank correction columns must be supplied together: "
                + ", ".join(BLANK_COLUMNS)
            )

        trials: list[PairedTrial] = []
        seen_block_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"CSV row {row_number} has more fields than the header"
                )

            block_id = _required_text(row, "block_id", row_number)
            if block_id in seen_block_ids:
                raise ValueError(
                    f"CSV row {row_number} duplicates block_id {block_id!r}"
                )
            seen_block_ids.add(block_id)

            independent_run_id = _required_text(
                row, "independent_run_id", row_number
            )
            data_provenance = _required_text(
                row, "data_provenance", row_number
            ).lower()
            if data_provenance not in DATA_PROVENANCES:
                raise ValueError(
                    f"{_row_name(row_number, 'data_provenance')} must be one of "
                    + ", ".join(DATA_PROVENANCES)
                )

            randomized_order = _required_text(
                row, "randomized_order", row_number
            ).lower()
            if randomized_order not in RANDOMIZED_ORDERS:
                raise ValueError(
                    f"{_row_name(row_number, 'randomized_order')} must be one of "
                    + ", ".join(RANDOMIZED_ORDERS)
                )

            off_blank: Optional[float] = None
            on_blank: Optional[float] = None
            if blank_header_count == 2:
                off_blank = _optional_number(
                    row,
                    "field_off_blank_count",
                    row_number,
                    minimum=0.0,
                )
                on_blank = _optional_number(
                    row,
                    "field_on_blank_count",
                    row_number,
                    minimum=0.0,
                )
                if (off_blank is None) != (on_blank is None):
                    raise ValueError(
                        f"CSV row {row_number} must provide both blank counts or "
                        "neither"
                    )

            trials.append(
                PairedTrial(
                    block_id=block_id,
                    independent_run_id=independent_run_id,
                    data_provenance=data_provenance,
                    randomized_order=randomized_order,
                    particle_nm=_number(
                        row,
                        "particle_nm",
                        row_number,
                        minimum=0.0,
                        minimum_inclusive=False,
                    ),
                    gas=_required_text(row, "gas", row_number),
                    flow_slm=_number(row, "flow_slm", row_number, minimum=0.0),
                    exposure_s=_number(
                        row,
                        "exposure_s",
                        row_number,
                        minimum=0.0,
                        minimum_inclusive=False,
                    ),
                    field_off_count=_number(
                        row,
                        "field_off_count",
                        row_number,
                        minimum=0.0,
                        minimum_inclusive=False,
                    ),
                    field_on_count=_number(
                        row,
                        "field_on_count",
                        row_number,
                        minimum=0.0,
                        minimum_inclusive=False,
                    ),
                    field_off_blank_count=off_blank,
                    field_on_blank_count=on_blank,
                    sampled_area_cm2=_optional_number(
                        row,
                        "sampled_area_cm2",
                        row_number,
                        minimum=0.0,
                        minimum_inclusive=False,
                    ),
                    temperature_c=_optional_number(
                        row, "temperature_c", row_number
                    ),
                    relative_humidity_pct=_optional_number(
                        row,
                        "relative_humidity_pct",
                        row_number,
                        minimum=0.0,
                        maximum=100.0,
                    ),
                    device_id=_optional_text(row, "device_id"),
                    trial_day=_optional_text(row, "trial_day"),
                    protocol_id=_optional_text(row, "protocol_id"),
                    aerosol_batch_id=_optional_text(row, "aerosol_batch_id"),
                    measurement_method_id=_optional_text(
                        row, "measurement_method_id"
                    ),
                    exclusion_policy_id=_optional_text(
                        row, "exclusion_policy_id"
                    ),
                    stopping_rule_id=_optional_text(row, "stopping_rule_id"),
                    replacement_policy_id=_optional_text(
                        row, "replacement_policy_id"
                    ),
                    notes=(row.get("notes") or "").strip(),
                )
            )

    if not trials:
        raise ValueError("CSV must contain at least one data row")
    return trials


def _validate_analysis_options(
    blank_policy: str,
    minimum_reduction_fraction: float,
    minimum_independent_runs: int,
    minimum_runs_per_order: int,
    minimum_order_balance_ratio: float,
    max_order_ratio_fold_difference: float,
    max_temperature_span_c: float,
    max_relative_humidity_span_pct: float,
    bootstrap_resamples: int,
    seed: int,
    gate_specification_confirmed: bool,
) -> None:
    if blank_policy not in BLANK_POLICIES:
        raise ValueError("blank_policy must be one of: " + ", ".join(BLANK_POLICIES))
    if not math.isfinite(minimum_reduction_fraction) or not (
        0.0 <= minimum_reduction_fraction < 1.0
    ):
        raise ValueError("minimum_reduction_fraction must be finite and in [0, 1)")
    if isinstance(minimum_independent_runs, bool) or not isinstance(
        minimum_independent_runs, int
    ):
        raise TypeError("minimum_independent_runs must be an integer")
    if minimum_independent_runs < 2:
        raise ValueError("minimum_independent_runs must be >= 2")
    if isinstance(minimum_runs_per_order, bool) or not isinstance(
        minimum_runs_per_order, int
    ):
        raise TypeError("minimum_runs_per_order must be an integer")
    if minimum_runs_per_order < 1:
        raise ValueError("minimum_runs_per_order must be >= 1")
    if minimum_independent_runs < 2 * minimum_runs_per_order:
        raise ValueError(
            "minimum_independent_runs must be at least twice "
            "minimum_runs_per_order"
        )
    if not math.isfinite(minimum_order_balance_ratio) or not (
        0.0 < minimum_order_balance_ratio <= 1.0
    ):
        raise ValueError("minimum_order_balance_ratio must be finite and in (0, 1]")
    if not math.isfinite(max_order_ratio_fold_difference) or (
        max_order_ratio_fold_difference < 1.0
    ):
        raise ValueError(
            "max_order_ratio_fold_difference must be finite and >= 1"
        )
    if not math.isfinite(max_temperature_span_c) or max_temperature_span_c < 0.0:
        raise ValueError("max_temperature_span_c must be finite and >= 0")
    if not math.isfinite(max_relative_humidity_span_pct) or (
        max_relative_humidity_span_pct < 0.0
    ):
        raise ValueError(
            "max_relative_humidity_span_pct must be finite and >= 0"
        )
    if isinstance(bootstrap_resamples, bool) or not isinstance(
        bootstrap_resamples, int
    ):
        raise TypeError("bootstrap_resamples must be an integer")
    if bootstrap_resamples < MINIMUM_BOOTSTRAP_RESAMPLES:
        raise ValueError(
            f"bootstrap_resamples must be >= {MINIMUM_BOOTSTRAP_RESAMPLES}"
        )
    if bootstrap_resamples > MAXIMUM_BOOTSTRAP_RESAMPLES:
        raise ValueError(
            f"bootstrap_resamples must be <= {MAXIMUM_BOOTSTRAP_RESAMPLES}"
        )
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if not isinstance(gate_specification_confirmed, bool):
        raise TypeError("gate_specification_confirmed must be boolean")


def _verify_locked_protocol_for_analysis(
    locked_protocol: Optional[dict[str, Any]],
    trials: Sequence[PairedTrial],
    *,
    blank_policy: str,
    minimum_reduction_fraction: float,
    minimum_independent_runs: int,
    minimum_runs_per_order: int,
    minimum_order_balance_ratio: float,
    max_order_ratio_fold_difference: float,
    max_temperature_span_c: float,
    max_relative_humidity_span_pct: float,
    bootstrap_resamples: int,
    seed: int,
) -> dict[str, Any]:
    """Verify a power-plan lock and bind it to this exact analysis invocation.

    A missing lock is represented in the audit document and prevents a gate
    pass.  A supplied but invalid, altered, or mismatched lock is an input
    error.  Re-verification here is intentional: callers of the Python API
    cannot bypass the check by constructing a truthy placeholder object.
    """

    if locked_protocol is None:
        return {
            "supplied": False,
            "machine_verified": False,
            "analysis_gate_options_match": False,
            "csv_protocol_id_match": False,
            "experimental_scope_match": False,
            "protocol_id": None,
            "canonical_sha256": None,
            "fingerprint_proves": None,
            "fingerprint_proves_chronology": False,
            "power_basis": "no_machine_verified_locked_protocol",
            "actual_bootstrap_gate_validated": False,
            "example_only": None,
            "execution_eligible": False,
        }
    if not isinstance(locked_protocol, dict):
        raise TypeError("locked_protocol must be a dictionary or None")

    verified = deposition_power.verify_locked_protocol(locked_protocol)
    protocol_metadata = verified["protocol"]
    if protocol_metadata.get("example_only") is not False:
        raise ValueError(
            "example-only locked protocol is a software fixture and cannot be "
            "used for deposition acceptance analysis"
        )
    if protocol_metadata.get("execution_eligible") is not True:
        raise ValueError(
            "locked protocol is not execution-eligible for deposition "
            "acceptance analysis"
        )
    planned_gate = verified["analysis_gate"]
    actual_gate = {
        "blank_policy": blank_policy,
        "minimum_reduction_fraction": minimum_reduction_fraction,
        "minimum_independent_runs": minimum_independent_runs,
        "minimum_runs_per_order": minimum_runs_per_order,
        "minimum_order_balance_ratio": minimum_order_balance_ratio,
        "max_order_ratio_fold_difference": max_order_ratio_fold_difference,
        "max_temperature_span_c": max_temperature_span_c,
        "max_relative_humidity_span_pct": max_relative_humidity_span_pct,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": seed,
    }
    option_mismatches = {
        name: {"locked": planned_gate.get(name), "analysis": actual_value}
        for name, actual_value in actual_gate.items()
        if planned_gate.get(name) != actual_value
    }
    if option_mismatches:
        rendered = ", ".join(sorted(option_mismatches))
        raise ValueError(
            "locked protocol analysis_gate does not match analysis option(s): "
            + rendered
        )

    planned_protocol_id = verified["protocol"]["protocol_id"]
    observed_protocol_ids = {trial.protocol_id for trial in trials}
    if observed_protocol_ids != {planned_protocol_id}:
        rendered_ids = sorted(
            "<missing>" if value is None else value
            for value in observed_protocol_ids
        )
        raise ValueError(
            "CSV protocol_id must be present, singular, and equal the locked "
            f"protocol_id {planned_protocol_id!r}; observed: {rendered_ids}"
        )

    planned_inputs = verified["planning_inputs"]
    scope_attributes = {
        "device_id": "device_id",
        "particle_nm": "particle_nm",
        "gas": "gas",
        "flow_slm": "flow_slm",
        "exposure_s": "exposure_s",
        "sampled_area_cm2": "sampled_area_cm2",
        "measurement_method_id": "measurement_method_id",
        "exclusion_policy_id": "exclusion_policy_id",
        "stopping_rule_id": "stopping_rule_id",
        "replacement_policy_id": "replacement_policy_id",
    }
    scope_mismatches: dict[str, dict[str, Any]] = {}
    for plan_name, trial_attribute in scope_attributes.items():
        observed_values = {
            getattr(trial, trial_attribute) for trial in trials
        }
        planned_value = planned_inputs[plan_name]
        if observed_values != {planned_value}:
            scope_mismatches[plan_name] = {
                "locked": planned_value,
                "observed": sorted(
                    "<missing>" if value is None else repr(value)
                    for value in observed_values
                ),
            }
    if scope_mismatches:
        raise ValueError(
            "CSV experimental scope does not exactly match locked protocol field(s): "
            + ", ".join(sorted(scope_mismatches))
        )

    fingerprint = verified["protocol_fingerprint"]
    return {
        "supplied": True,
        "machine_verified": True,
        "analysis_gate_options_match": True,
        "csv_protocol_id_match": True,
        "experimental_scope_match": True,
        "protocol_id": planned_protocol_id,
        "canonical_sha256": fingerprint["canonical_sha256"],
        "fingerprint_algorithm": fingerprint["algorithm"],
        "fingerprint_canonicalization": fingerprint["canonicalization"],
        "fingerprint_proves": fingerprint["proves"],
        "fingerprint_does_not_prove": fingerprint["does_not_prove"],
        "fingerprint_proves_chronology": False,
        "power_calculations_reproduced": True,
        "power_basis": "surrogate_power_only",
        "actual_bootstrap_gate_validated": False,
        "example_only": False,
        "execution_eligible": True,
        "planning_assumptions_authenticated": False,
        "prospective_only_declared": verified["protocol"]["prospective_only"],
        "hardware_performance_validated_by_plan": verified["protocol"][
            "hardware_performance_validated"
        ],
        "locked_analysis_gate": dict(planned_gate),
        "locked_experimental_scope": {
            name: planned_inputs[name] for name in scope_attributes
        },
    }


def _bootstrap_mean_log_ratios(
    log_ratios: np.ndarray,
    bootstrap_resamples: int,
    seed: int,
) -> np.ndarray:
    """Bootstrap supplied log-ratio units, chunked to bound memory use."""

    generator = np.random.default_rng(seed)
    block_count = int(log_ratios.size)
    mean_log_ratios = np.empty(bootstrap_resamples, dtype=float)
    max_index_values_per_chunk = 2_000_000
    chunk_size = max(
        1, min(bootstrap_resamples, max_index_values_per_chunk // block_count)
    )
    for start in range(0, bootstrap_resamples, chunk_size):
        stop = min(start + chunk_size, bootstrap_resamples)
        indices = generator.integers(
            0, block_count, size=(stop - start, block_count)
        )
        mean_log_ratios[start:stop] = np.mean(log_ratios[indices], axis=1)
    if not np.all(np.isfinite(mean_log_ratios)):
        raise ValueError("bootstrap produced non-finite results; inspect count scale")
    return mean_log_ratios


def _bootstrap_interval_document(mean_log_ratio_samples: np.ndarray) -> dict[str, Any]:
    """Return log/reduction percentile intervals plus approximate quantile MC error."""

    log_ci_lower, log_ci_upper = (
        float(value)
        for value in np.percentile(mean_log_ratio_samples, (2.5, 97.5))
    )
    reduction_ci_lower = 1.0 - math.exp(log_ci_upper)
    reduction_ci_upper = 1.0 - math.exp(log_ci_lower)

    batch_count = min(20, max(2, int(mean_log_ratio_samples.size) // 500))
    batch_lower_endpoints = []
    for batch in np.array_split(mean_log_ratio_samples, batch_count):
        batch_log_upper = float(np.percentile(batch, 97.5))
        batch_lower_endpoints.append(1.0 - math.exp(batch_log_upper))
    mc_standard_error = float(
        np.std(np.asarray(batch_lower_endpoints), ddof=1) / math.sqrt(batch_count)
    )
    mc_guard_half_width = max(MONTE_CARLO_GUARD_Z * mc_standard_error, 1e-12)
    return {
        "mean_log_ratio": {
            "lower": log_ci_lower,
            "upper": log_ci_upper,
        },
        "reduction_fraction": {
            "lower": reduction_ci_lower,
            "upper": reduction_ci_upper,
        },
        "lower_endpoint_monte_carlo": {
            "method": "batch_quantile_standard_error",
            "batch_count": batch_count,
            "standard_error": mc_standard_error,
            "guard_z": MONTE_CARLO_GUARD_Z,
            "guard_half_width": mc_guard_half_width,
        },
    }


def _condition_document(trial: PairedTrial) -> dict[str, Any]:
    return {
        "particle_nm": trial.particle_nm,
        "gas": trial.gas,
        "flow_slm": trial.flow_slm,
        "exposure_s": trial.exposure_s,
        "sampled_area_cm2": trial.sampled_area_cm2,
        "temperature_c": trial.temperature_c,
        "relative_humidity_pct": trial.relative_humidity_pct,
    }


def _traceability_document(trial: PairedTrial) -> dict[str, Optional[str]]:
    return {
        "device_id": trial.device_id,
        "trial_day": trial.trial_day,
        "protocol_id": trial.protocol_id,
        "aerosol_batch_id": trial.aerosol_batch_id,
        "measurement_method_id": trial.measurement_method_id,
        "exclusion_policy_id": trial.exclusion_policy_id,
        "stopping_rule_id": trial.stopping_rule_id,
        "replacement_policy_id": trial.replacement_policy_id,
    }


def _validate_trial_object(trial: PairedTrial) -> None:
    """Apply CSV-equivalent validation to callers using the Python API."""

    if not isinstance(trial.block_id, str) or not trial.block_id.strip():
        raise ValueError("every trial must have a non-empty string block_id")
    if (
        not isinstance(trial.independent_run_id, str)
        or not trial.independent_run_id.strip()
    ):
        raise ValueError(
            f"block {trial.block_id!r} must have a non-empty independent_run_id"
        )
    if trial.data_provenance not in DATA_PROVENANCES:
        raise ValueError(
            f"block {trial.block_id!r} data_provenance must be one of: "
            + ", ".join(DATA_PROVENANCES)
        )
    if not isinstance(trial.gas, str) or not trial.gas.strip():
        raise ValueError(f"block {trial.block_id!r} must have a non-empty gas")
    if trial.randomized_order not in RANDOMIZED_ORDERS:
        raise ValueError(f"invalid randomized_order in block {trial.block_id!r}")

    finite_positive = {
        "particle_nm": trial.particle_nm,
        "exposure_s": trial.exposure_s,
        "field_off_count": trial.field_off_count,
        "field_on_count": trial.field_on_count,
    }
    for name, value in finite_positive.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"block {trial.block_id!r} {name} must be numeric")
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"block {trial.block_id!r} {name} must be finite and > 0")

    if (
        not isinstance(trial.flow_slm, (int, float))
        or isinstance(trial.flow_slm, bool)
        or not math.isfinite(trial.flow_slm)
        or trial.flow_slm < 0.0
    ):
        raise ValueError(f"block {trial.block_id!r} flow_slm must be finite and >= 0")

    if (trial.field_off_blank_count is None) != (
        trial.field_on_blank_count is None
    ):
        raise ValueError(
            f"block {trial.block_id!r} must provide both blanks or neither"
        )
    for name, value in (
        ("field_off_blank_count", trial.field_off_blank_count),
        ("field_on_blank_count", trial.field_on_blank_count),
    ):
        if value is not None and (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0.0
        ):
            raise ValueError(
                f"block {trial.block_id!r} {name} must be finite and >= 0"
            )

    if trial.sampled_area_cm2 is not None and (
        not isinstance(trial.sampled_area_cm2, (int, float))
        or isinstance(trial.sampled_area_cm2, bool)
        or not math.isfinite(trial.sampled_area_cm2)
        or trial.sampled_area_cm2 <= 0.0
    ):
        raise ValueError(
            f"block {trial.block_id!r} sampled_area_cm2 must be finite and > 0"
        )
    if trial.temperature_c is not None and (
        not isinstance(trial.temperature_c, (int, float))
        or isinstance(trial.temperature_c, bool)
        or not math.isfinite(trial.temperature_c)
    ):
        raise ValueError(f"block {trial.block_id!r} temperature_c must be finite")
    if trial.relative_humidity_pct is not None and (
        not isinstance(trial.relative_humidity_pct, (int, float))
        or isinstance(trial.relative_humidity_pct, bool)
        or not math.isfinite(trial.relative_humidity_pct)
        or not 0.0 <= trial.relative_humidity_pct <= 100.0
    ):
        raise ValueError(
            f"block {trial.block_id!r} relative_humidity_pct must be in [0, 100]"
        )
    for name, value in _traceability_document(trial).items():
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError(
                f"block {trial.block_id!r} {name} must be non-empty text when set"
            )


def analyze_trials(
    trials: Sequence[PairedTrial],
    *,
    blank_policy: str = BLANK_POLICY_NONE,
    minimum_reduction_fraction: float = DEFAULT_MINIMUM_REDUCTION_FRACTION,
    minimum_independent_runs: int = DEFAULT_MINIMUM_INDEPENDENT_RUNS,
    minimum_runs_per_order: int = DEFAULT_MINIMUM_RUNS_PER_ORDER,
    minimum_order_balance_ratio: float = DEFAULT_MINIMUM_ORDER_BALANCE_RATIO,
    max_order_ratio_fold_difference: float = (
        DEFAULT_MAX_ORDER_RATIO_FOLD_DIFFERENCE
    ),
    max_temperature_span_c: float = DEFAULT_MAX_TEMPERATURE_SPAN_C,
    max_relative_humidity_span_pct: float = (
        DEFAULT_MAX_RELATIVE_HUMIDITY_SPAN_PCT
    ),
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    gate_specification_confirmed: bool = False,
    locked_protocol: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Analyze paired blocks and return a conservative audit document.

    Independent runs, not CSV rows, are the resampling and sample-size units.
    A performance gate can pass only for experimental data when a valid,
    non-example, execution-eligible power protocol is supplied, its fingerprint,
    options, and protocol identifier match,
    all thresholds were locked before unblinding, both randomized orders are
    adequately represented and consistent, at least 10,000 bootstrap resamples
    were used, and no unmodelled paired-blank subtraction was applied.
    """

    _validate_analysis_options(
        blank_policy,
        minimum_reduction_fraction,
        minimum_independent_runs,
        minimum_runs_per_order,
        minimum_order_balance_ratio,
        max_order_ratio_fold_difference,
        max_temperature_span_c,
        max_relative_humidity_span_pct,
        bootstrap_resamples,
        seed,
        gate_specification_confirmed,
    )
    if not trials:
        raise ValueError("at least one paired block is required")
    if not all(isinstance(trial, PairedTrial) for trial in trials):
        raise TypeError("trials must contain only PairedTrial values")
    for trial in trials:
        _validate_trial_object(trial)

    locked_protocol_verification = _verify_locked_protocol_for_analysis(
        locked_protocol,
        trials,
        blank_policy=blank_policy,
        minimum_reduction_fraction=minimum_reduction_fraction,
        minimum_independent_runs=minimum_independent_runs,
        minimum_runs_per_order=minimum_runs_per_order,
        minimum_order_balance_ratio=minimum_order_balance_ratio,
        max_order_ratio_fold_difference=max_order_ratio_fold_difference,
        max_temperature_span_c=max_temperature_span_c,
        max_relative_humidity_span_pct=max_relative_humidity_span_pct,
        bootstrap_resamples=bootstrap_resamples,
        seed=seed,
    )
    locked_protocol_verified = locked_protocol_verification["machine_verified"]

    provenance_values = {trial.data_provenance for trial in trials}
    if len(provenance_values) != 1:
        raise ValueError("one analysis cannot mix synthetic and experimental provenance")
    data_provenance = next(iter(provenance_values))

    stratum_keys = {
        (
            trial.particle_nm,
            trial.gas.casefold(),
            trial.flow_slm,
            trial.exposure_s,
            trial.sampled_area_cm2,
        )
        for trial in trials
    }
    if len(stratum_keys) != 1:
        rendered_strata = sorted(
            (
                {
                    "particle_nm": particle_nm,
                    "gas": gas,
                    "flow_slm": flow_slm,
                    "exposure_s": exposure_s,
                    "sampled_area_cm2": sampled_area_cm2,
                }
                for (
                    particle_nm,
                    gas,
                    flow_slm,
                    exposure_s,
                    sampled_area_cm2,
                ) in stratum_keys
            ),
            key=repr,
        )
        raise ValueError(
            "one analysis may contain only one particle/gas/flow/exposure/area "
            "stratum; "
            f"split the CSV before analysis (observed: {rendered_strata})"
        )

    pair_documents: list[dict[str, Any]] = []
    run_groups: dict[str, dict[str, Any]] = {}
    pair_order_counts = {order: 0 for order in RANDOMIZED_ORDERS}
    seen_ids: set[str] = set()

    for trial in trials:
        if trial.block_id in seen_ids:
            raise ValueError(f"duplicate block_id {trial.block_id!r}")
        seen_ids.add(trial.block_id)
        pair_order_counts[trial.randomized_order] += 1

        run_group = run_groups.setdefault(
            trial.independent_run_id,
            {
                "randomized_order": trial.randomized_order,
                "traceability": _traceability_document(trial),
                "log_ratios": [],
                "block_ids": [],
            },
        )
        if run_group["randomized_order"] != trial.randomized_order:
            raise ValueError(
                f"independent_run_id {trial.independent_run_id!r} contains both "
                "randomized orders; split or correct the run record"
            )
        if run_group["traceability"] != _traceability_document(trial):
            raise ValueError(
                f"independent_run_id {trial.independent_run_id!r} contains "
                "inconsistent traceability or experimental-scope metadata"
            )

        if blank_policy == BLANK_POLICY_PAIRED_SUBTRACT:
            if (
                trial.field_off_blank_count is None
                or trial.field_on_blank_count is None
            ):
                raise ValueError(
                    f"block {trial.block_id!r} lacks paired blanks required by "
                    f"blank_policy={BLANK_POLICY_PAIRED_SUBTRACT!r}"
                )
            corrected_off = trial.field_off_count - trial.field_off_blank_count
            corrected_on = trial.field_on_count - trial.field_on_blank_count
            applied_off_blank = trial.field_off_blank_count
            applied_on_blank = trial.field_on_blank_count
        else:
            corrected_off = trial.field_off_count
            corrected_on = trial.field_on_count
            applied_off_blank = 0.0
            applied_on_blank = 0.0

        if not math.isfinite(corrected_off) or corrected_off <= 0.0:
            raise ValueError(
                f"block {trial.block_id!r} has non-positive field-OFF count after "
                "blank correction; no pseudocount was applied"
            )
        if not math.isfinite(corrected_on) or corrected_on <= 0.0:
            raise ValueError(
                f"block {trial.block_id!r} has non-positive field-ON count after "
                "blank correction; no pseudocount was applied"
            )

        ratio = corrected_on / corrected_off
        if not math.isfinite(ratio) or ratio <= 0.0:
            raise ValueError(
                f"block {trial.block_id!r} produced an invalid count ratio"
            )
        log_ratio = math.log(corrected_on) - math.log(corrected_off)
        run_group["log_ratios"].append(log_ratio)
        run_group["block_ids"].append(trial.block_id)
        pair_documents.append(
            {
                "block_id": trial.block_id,
                "independent_run_id": trial.independent_run_id,
                "data_provenance": trial.data_provenance,
                "randomized_order": trial.randomized_order,
                "condition": _condition_document(trial),
                "traceability": _traceability_document(trial),
                "raw": {
                    "field_off_count": trial.field_off_count,
                    "field_on_count": trial.field_on_count,
                    "field_off_blank_count": trial.field_off_blank_count,
                    "field_on_blank_count": trial.field_on_blank_count,
                },
                "blank_applied": {
                    "field_off_count": applied_off_blank,
                    "field_on_count": applied_on_blank,
                },
                "corrected": {
                    "field_off_count": corrected_off,
                    "field_on_count": corrected_on,
                },
                "field_on_to_off_ratio": ratio,
                "pair_log_ratio": log_ratio,
                "pair_deposition_reduction_fraction": 1.0 - ratio,
                "notes": trial.notes,
            }
        )

    independent_run_documents: list[dict[str, Any]] = []
    run_mean_log_ratios: list[float] = []
    order_run_log_ratios: dict[str, list[float]] = {
        order: [] for order in RANDOMIZED_ORDERS
    }
    for independent_run_id, group in run_groups.items():
        run_mean_log_ratio = float(np.mean(np.asarray(group["log_ratios"])))
        run_mean_log_ratios.append(run_mean_log_ratio)
        order_run_log_ratios[group["randomized_order"]].append(run_mean_log_ratio)
        run_ratio = math.exp(run_mean_log_ratio)
        independent_run_documents.append(
            {
                "independent_run_id": independent_run_id,
                "randomized_order": group["randomized_order"],
                "paired_block_count": len(group["block_ids"]),
                "block_ids": group["block_ids"],
                "traceability": group["traceability"],
                "mean_pair_log_ratio": run_mean_log_ratio,
                "geometric_mean_field_on_to_off_ratio": run_ratio,
                "geometric_mean_deposition_reduction_fraction": 1.0 - run_ratio,
            }
        )

    run_log_ratio_array = np.asarray(run_mean_log_ratios, dtype=float)
    mean_log_ratio = float(np.mean(run_log_ratio_array))
    geometric_mean_ratio = math.exp(mean_log_ratio)
    geometric_mean_reduction = 1.0 - geometric_mean_ratio

    bootstrap_mean_log_ratios = _bootstrap_mean_log_ratios(
        run_log_ratio_array, bootstrap_resamples, seed
    )
    interval = _bootstrap_interval_document(bootstrap_mean_log_ratios)
    reduction_ci_lower = interval["reduction_fraction"]["lower"]
    reduction_ci_upper = interval["reduction_fraction"]["upper"]

    independent_run_count = len(run_groups)
    independent_run_requirement_met = (
        independent_run_count >= minimum_independent_runs
    )
    independent_order_counts = {
        order: len(order_run_log_ratios[order]) for order in RANDOMIZED_ORDERS
    }
    if locked_protocol_verified:
        locked_gate = locked_protocol_verification["locked_analysis_gate"]
        exact_locked_total_count_met = (
            independent_run_count == locked_gate["minimum_independent_runs"]
        )
        exact_locked_order_counts_met = all(
            independent_order_counts[order]
            == locked_gate["minimum_runs_per_order"]
            for order in RANDOMIZED_ORDERS
        )
    else:
        exact_locked_total_count_met = False
        exact_locked_order_counts_met = False
    exact_locked_sample_size_and_allocation_met = (
        exact_locked_total_count_met and exact_locked_order_counts_met
    )
    order_representation_met = all(
        count >= minimum_runs_per_order
        for count in independent_order_counts.values()
    )
    maximum_order_count = max(independent_order_counts.values())
    minimum_order_count = min(independent_order_counts.values())
    observed_order_balance_ratio = (
        minimum_order_count / maximum_order_count
        if maximum_order_count > 0
        else 0.0
    )
    order_balance_met = (
        observed_order_balance_ratio >= minimum_order_balance_ratio
    )

    order_diagnostics: dict[str, Any] = {}
    for order_index, order in enumerate(RANDOMIZED_ORDERS, start=1):
        order_values = np.asarray(order_run_log_ratios[order], dtype=float)
        if order_values.size == 0:
            order_diagnostics[order] = {
                "independent_run_count": 0,
                "mean_log_ratio": None,
                "geometric_mean_field_on_to_off_ratio": None,
                "geometric_mean_deposition_reduction_fraction": None,
                "bootstrap_95_percent_ci": None,
                "effect_requirement_met": False,
                "monte_carlo_boundary_indeterminate": False,
            }
            continue
        order_mean_log_ratio = float(np.mean(order_values))
        order_ratio = math.exp(order_mean_log_ratio)
        order_samples = _bootstrap_mean_log_ratios(
            order_values, bootstrap_resamples, seed + order_index
        )
        order_interval = _bootstrap_interval_document(order_samples)
        order_lower = order_interval["reduction_fraction"]["lower"]
        order_guard = order_interval["lower_endpoint_monte_carlo"][
            "guard_half_width"
        ]
        order_diagnostics[order] = {
            "independent_run_count": int(order_values.size),
            "mean_log_ratio": order_mean_log_ratio,
            "geometric_mean_field_on_to_off_ratio": order_ratio,
            "geometric_mean_deposition_reduction_fraction": 1.0 - order_ratio,
            "bootstrap_95_percent_ci": order_interval,
            "effect_requirement_met": order_lower
            >= minimum_reduction_fraction,
            "monte_carlo_boundary_indeterminate": abs(
                order_lower - minimum_reduction_fraction
            )
            <= order_guard,
        }

    order_effect_requirement_met = all(
        order_diagnostics[order]["effect_requirement_met"]
        for order in RANDOMIZED_ORDERS
    )
    if all(order_run_log_ratios[order] for order in RANDOMIZED_ORDERS):
        order_log_ratio_difference = abs(
            order_diagnostics["off_then_on"]["mean_log_ratio"]
            - order_diagnostics["on_then_off"]["mean_log_ratio"]
        )
        observed_order_ratio_fold_difference = math.exp(
            order_log_ratio_difference
        )
        order_consistency_met = (
            observed_order_ratio_fold_difference
            <= max_order_ratio_fold_difference
        )
    else:
        order_log_ratio_difference = None
        observed_order_ratio_fold_difference = None
        order_consistency_met = False

    effect_passed = reduction_ci_lower >= minimum_reduction_fraction
    bootstrap_requirement_met = (
        bootstrap_resamples >= MINIMUM_GATE_BOOTSTRAP_RESAMPLES
    )
    global_mc_guard = interval["lower_endpoint_monte_carlo"][
        "guard_half_width"
    ]
    boundary_indeterminate = abs(
        reduction_ci_lower - minimum_reduction_fraction
    ) <= global_mc_guard or any(
        order_diagnostics[order]["monte_carlo_boundary_indeterminate"]
        for order in RANDOMIZED_ORDERS
    )
    synthetic_demonstration = data_provenance == "synthetic"
    blank_uncertainty_unmodelled = (
        blank_policy == BLANK_POLICY_PAIRED_SUBTRACT
    )
    missing_traceability_by_block = {
        trial.block_id: [
            name
            for name, value in _traceability_document(trial).items()
            if value is None
        ]
        for trial in trials
        if any(value is None for value in _traceability_document(trial).values())
    }
    traceability_complete = not missing_traceability_by_block
    measurement_context_complete = all(
        trial.sampled_area_cm2 is not None
        and trial.temperature_c is not None
        and trial.relative_humidity_pct is not None
        for trial in trials
    )
    if measurement_context_complete:
        temperatures = [float(trial.temperature_c) for trial in trials]
        humidities = [float(trial.relative_humidity_pct) for trial in trials]
        temperature_span_c: Optional[float] = max(temperatures) - min(temperatures)
        humidity_span_pct: Optional[float] = max(humidities) - min(humidities)
        environment_tolerance_met = (
            temperature_span_c <= max_temperature_span_c
            and humidity_span_pct <= max_relative_humidity_span_pct
        )
    else:
        temperatures = []
        humidities = []
        temperature_span_c = None
        humidity_span_pct = None
        environment_tolerance_met = False

    unique_device_ids = sorted(
        {trial.device_id for trial in trials if trial.device_id is not None}
    )
    unique_protocol_ids = sorted(
        {trial.protocol_id for trial in trials if trial.protocol_id is not None}
    )
    unique_trial_days = sorted(
        {trial.trial_day for trial in trials if trial.trial_day is not None}
    )
    unique_aerosol_batches = sorted(
        {
            trial.aerosol_batch_id
            for trial in trials
            if trial.aerosol_batch_id is not None
        }
    )
    unique_measurement_method_ids = sorted(
        {
            trial.measurement_method_id
            for trial in trials
            if trial.measurement_method_id is not None
        }
    )
    unique_exclusion_policy_ids = sorted(
        {
            trial.exclusion_policy_id
            for trial in trials
            if trial.exclusion_policy_id is not None
        }
    )
    unique_stopping_rule_ids = sorted(
        {
            trial.stopping_rule_id
            for trial in trials
            if trial.stopping_rule_id is not None
        }
    )
    unique_replacement_policy_ids = sorted(
        {
            trial.replacement_policy_id
            for trial in trials
            if trial.replacement_policy_id is not None
        }
    )
    single_device_and_protocol = (
        traceability_complete
        and len(unique_device_ids) == 1
        and len(unique_protocol_ids) == 1
    )

    gate_failure_reasons: list[str] = []
    if synthetic_demonstration:
        gate_failure_reasons.append("synthetic_data_is_demonstration_only")
    if blank_uncertainty_unmodelled:
        gate_failure_reasons.append(
            "paired_blank_uncertainty_is_not_modelled_for_acceptance"
        )
    if not gate_specification_confirmed:
        gate_failure_reasons.append("gate_was_not_confirmed_prespecified")
    if not locked_protocol_verified:
        gate_failure_reasons.append("machine_verified_locked_protocol_was_not_supplied")
    elif not exact_locked_sample_size_and_allocation_met:
        gate_failure_reasons.append(
            "observed_independent_run_counts_do_not_equal_locked_plan"
        )
    if not bootstrap_requirement_met:
        gate_failure_reasons.append("fewer_than_10000_gate_bootstrap_resamples")
    if not independent_run_requirement_met:
        gate_failure_reasons.append("insufficient_unique_independent_runs")
    if not order_representation_met:
        gate_failure_reasons.append("insufficient_runs_in_one_or_both_orders")
    if not order_balance_met:
        gate_failure_reasons.append("randomized_order_allocation_is_imbalanced")
    if not traceability_complete:
        gate_failure_reasons.append(
            "required_traceability_or_experimental_scope_metadata_missing"
        )
    if not single_device_and_protocol:
        gate_failure_reasons.append("multiple_or_missing_device_or_protocol_ids")
    if not measurement_context_complete:
        gate_failure_reasons.append("area_temperature_or_humidity_missing")
    if not environment_tolerance_met:
        gate_failure_reasons.append("environment_span_exceeds_prespecified_limit")
    if boundary_indeterminate:
        gate_failure_reasons.append("gate_boundary_within_monte_carlo_guard")
    if not effect_passed:
        gate_failure_reasons.append("overall_ci_lower_bound_below_threshold")
    if not order_effect_requirement_met:
        gate_failure_reasons.append("one_or_both_order_specific_effects_fail")
    if not order_consistency_met:
        gate_failure_reasons.append("order_specific_effects_are_inconsistent")

    if synthetic_demonstration:
        gate_status = "demonstration_only"
    elif blank_uncertainty_unmodelled:
        gate_status = "diagnostic_only_blank_uncertainty_unmodelled"
    elif not gate_specification_confirmed:
        gate_status = "indeterminate_not_prespecified"
    elif not locked_protocol_verified:
        gate_status = "indeterminate_no_machine_verified_locked_protocol"
    elif not exact_locked_sample_size_and_allocation_met:
        gate_status = "fail_locked_sample_size_or_allocation"
    elif not bootstrap_requirement_met:
        gate_status = "indeterminate_insufficient_bootstrap"
    elif not independent_run_requirement_met:
        gate_status = "insufficient_independent_runs"
    elif not order_representation_met:
        gate_status = "insufficient_order_representation"
    elif not order_balance_met:
        gate_status = "fail_order_balance"
    elif not traceability_complete:
        gate_status = "insufficient_traceability_metadata"
    elif not single_device_and_protocol:
        gate_status = "unsupported_device_or_protocol_pooling"
    elif not measurement_context_complete:
        gate_status = "insufficient_measurement_context"
    elif not environment_tolerance_met:
        gate_status = "fail_environment_tolerance"
    elif boundary_indeterminate:
        gate_status = "indeterminate_monte_carlo_boundary"
    elif not effect_passed:
        gate_status = "fail_effect"
    elif not order_effect_requirement_met:
        gate_status = "fail_order_specific_effect"
    elif not order_consistency_met:
        gate_status = "fail_order_inconsistency"
    else:
        gate_status = "pass"
    gate_passed = gate_status == "pass"
    eligible_for_dataset_rule_evaluation = (
        data_provenance == "experimental"
        and not blank_uncertainty_unmodelled
        and gate_specification_confirmed
        and locked_protocol_verified
        and exact_locked_sample_size_and_allocation_met
        and bootstrap_requirement_met
        and independent_run_requirement_met
        and order_representation_met
        and order_balance_met
        and traceability_complete
        and single_device_and_protocol
        and measurement_context_complete
        and environment_tolerance_met
    )

    unique_conditions: list[dict[str, Any]] = []
    observed_condition_keys: set[tuple[Any, ...]] = set()
    for trial in trials:
        condition = _condition_document(trial)
        key = tuple(condition.values())
        if key not in observed_condition_keys:
            observed_condition_keys.add(key)
            unique_conditions.append(condition)

    caveats = [
        "Each row must pair OFF and ON measurements under the same aerosol challenge, "
        "sampled area, exposure, detector, and operating conditions. Randomized order "
        "reduces but does not eliminate drift, carryover, or hysteresis.",
        "The geometric mean equally weights unique independent_run_id clusters after "
        "averaging repeated paired blocks within each run. This tool rejects mixed "
        "particle-size/gas/flow/exposure/sampled-area strata.",
        "Paired blank subtraction treats each blank as exact and does not propagate "
        "blank measurement uncertainty. Non-positive corrected counts fail instead "
        "of receiving an unplanned pseudocount. Because repeated-blank uncertainty is "
        "not modelled, paired_subtract results are diagnostic only and cannot pass the "
        "dataset decision rule.",
        "The percentile bootstrap resamples unique independent runs and does not fit a "
        "hierarchical model or account for cross-run dependence, instrument calibration "
        "error, or site-to-site variation.",
        "The reduction threshold is a user-prespecified decision rule. A gate also "
        "requires a machine-verified locked power protocol whose protocol_id and all "
        "analysis-gate options and experimental-scope fields exactly match this dataset "
        "and invocation. Eligible independent-run counts must equal, not merely exceed, "
        "the locked total and per-order counts.",
        "The protocol SHA-256 fingerprint proves content identity only. It does not prove "
        "when the protocol was created, who created it, whether it was registered before "
        "outcome access, or whether execution followed it. --confirm-prespecified-gate "
        "remains an explicit chronology self-attestation; retain an external timestamped "
        "registry and signed execution/deviation records.",
        "Machine verification reproduces the planner calculations and option bindings; "
        "it does not authenticate the assumed effect, SD, pilot provenance, or their "
        "fitness for this hardware and experiment.",
        "The locked power basis is a known-SD Normal z-bound surrogate, not calibrated "
        "power for this analyzer's percentile-bootstrap gate. A dataset-level gate pass "
        "therefore does not prove 80% actual-gate power or hardware performance.",
        "The randomized_order field records execution order but cannot prove that "
        "allocation was random; retain the randomization schedule and deviations in "
        "the trial record.",
        "Device, trial-day, protocol, aerosol-batch, measurement-method, exclusion, "
        "stopping, and replacement-policy identifiers are required for "
        "acceptance traceability. Missing values or pooled devices/protocols block the "
        "gate. Multiple days and aerosol batches are reported as diversity diagnostics, "
        "but this analysis does not estimate day or batch effects.",
        "Rule identifiers bind declared protocol content but cannot prove that exclusions, "
        "replacements, or stopping were executed as declared. Retain a blinded run ledger "
        "and signed deviation log; unreported excluded runs remain undetectable here.",
        "Temperature and humidity limits are user-prespecified engineering spans, not "
        "universal validity bounds. Missing measurements or spans over those limits block "
        "acceptance instead of fitting an unplanned environmental model.",
        "The batch estimate of bootstrap-quantile Monte Carlo error is approximate. A "
        "lower confidence endpoint inside its guard band is indeterminate, never a pass.",
        "Synthetic rows are demonstration-only regardless of their numerical effect and "
        "can never pass the dataset decision rule.",
        "A gate pass validates this dataset against the stated analysis rule only. It "
        "does not validate Aegis device performance; independent blinded and "
        "replicated hardware trials remain necessary.",
    ]

    report: dict[str, Any] = {
        "schema_version": 2,
        "analysis": {
            "data_provenance": data_provenance,
            "primary_pair_statistic": (
                "natural_log(field_on_corrected / field_off_corrected)"
            ),
            "independent_run_statistic": "mean(pair_log_ratio within run)",
            "aggregate": "exp(mean(independent_run_mean_log_ratio))",
            "independent_run_weighting": "equal",
            "reduction_definition": "1 - geometric_mean_field_on_to_off_ratio",
            "blank_policy": blank_policy,
            "implicit_pseudocount": None,
        },
        "design": {
            "design_type": "randomized_paired_blocks",
            "paired_block_count": len(trials),
            "unique_independent_run_count": independent_run_count,
            "minimum_independent_runs_for_gate": minimum_independent_runs,
            "sufficient_independent_runs_for_gate": (
                independent_run_requirement_met
            ),
            "paired_block_randomized_order_counts": pair_order_counts,
            "independent_run_randomized_order_counts": independent_order_counts,
            "minimum_runs_per_order": minimum_runs_per_order,
            "minimum_order_balance_ratio": minimum_order_balance_ratio,
            "observed_order_balance_ratio": observed_order_balance_ratio,
            "order_representation_met": order_representation_met,
            "order_balance_met": order_balance_met,
            "exact_locked_total_count_met": exact_locked_total_count_met,
            "exact_locked_order_counts_met": exact_locked_order_counts_met,
            "exact_locked_sample_size_and_allocation_met": (
                exact_locked_sample_size_and_allocation_met
            ),
            "analysis_stratum": {
                "particle_nm": trials[0].particle_nm,
                "gas": trials[0].gas,
                "flow_slm": trials[0].flow_slm,
                "exposure_s": trials[0].exposure_s,
                "sampled_area_cm2": trials[0].sampled_area_cm2,
            },
            "observed_measurement_settings": unique_conditions,
            "observed_measurement_setting_count": len(unique_conditions),
        },
        "pairs": pair_documents,
        "independent_runs": independent_run_documents,
        "summary": {
            "mean_independent_run_log_ratio": mean_log_ratio,
            "geometric_mean_field_on_to_off_ratio": geometric_mean_ratio,
            "geometric_mean_deposition_reduction_fraction": geometric_mean_reduction,
            "geometric_mean_deposition_reduction_percent": 100.0
            * geometric_mean_reduction,
            "bootstrap_95_percent_ci_mean_log_ratio": interval[
                "mean_log_ratio"
            ],
            "bootstrap_95_percent_ci_reduction_fraction": {
                "lower": reduction_ci_lower,
                "upper": reduction_ci_upper,
            },
            "lower_ci_endpoint_monte_carlo": interval[
                "lower_endpoint_monte_carlo"
            ],
        },
        "bootstrap": {
            "method": "independent_run_cluster_percentile",
            "cluster_statistic": "mean pair log ratio within independent_run_id",
            "confidence_level": 0.95,
            "resamples": bootstrap_resamples,
            "seed": seed,
            "minimum_resamples_for_gate": MINIMUM_GATE_BOOTSTRAP_RESAMPLES,
            "maximum_resamples": MAXIMUM_BOOTSTRAP_RESAMPLES,
            "gate_resample_requirement_met": bootstrap_requirement_met,
        },
        "randomized_order_diagnostics": {
            "by_order": order_diagnostics,
            "absolute_mean_log_ratio_difference": order_log_ratio_difference,
            "observed_ratio_fold_difference": (
                observed_order_ratio_fold_difference
            ),
            "maximum_allowed_ratio_fold_difference": (
                max_order_ratio_fold_difference
            ),
            "order_specific_effect_requirement_met": (
                order_effect_requirement_met
            ),
            "order_consistency_requirement_met": order_consistency_met,
        },
        "traceability": {
            "fields_required_for_acceptance": list(TRACEABILITY_COLUMNS),
            "complete_for_all_blocks": traceability_complete,
            "missing_fields_by_block": missing_traceability_by_block,
            "unique_device_ids": unique_device_ids,
            "unique_protocol_ids": unique_protocol_ids,
            "unique_trial_days": unique_trial_days,
            "unique_aerosol_batch_ids": unique_aerosol_batches,
            "unique_measurement_method_ids": unique_measurement_method_ids,
            "unique_exclusion_policy_ids": unique_exclusion_policy_ids,
            "unique_stopping_rule_ids": unique_stopping_rule_ids,
            "unique_replacement_policy_ids": unique_replacement_policy_ids,
            "single_device_and_protocol_for_gate": single_device_and_protocol,
        },
        "locked_protocol_verification": locked_protocol_verification,
        "environment_diagnostics": {
            "measurement_context_complete": measurement_context_complete,
            "temperature_c": {
                "minimum": min(temperatures) if temperatures else None,
                "maximum": max(temperatures) if temperatures else None,
                "observed_span": temperature_span_c,
                "maximum_allowed_span": max_temperature_span_c,
            },
            "relative_humidity_pct": {
                "minimum": min(humidities) if humidities else None,
                "maximum": max(humidities) if humidities else None,
                "observed_span": humidity_span_pct,
                "maximum_allowed_span": max_relative_humidity_span_pct,
            },
            "tolerance_source": "user_prespecified_engineering_limit_not_universal",
            "tolerance_requirement_met": environment_tolerance_met,
        },
        "prespecified_gate": {
            "minimum_deposition_reduction_fraction": minimum_reduction_fraction,
            "minimum_independent_runs": minimum_independent_runs,
            "minimum_runs_per_order": minimum_runs_per_order,
            "minimum_order_balance_ratio": minimum_order_balance_ratio,
            "maximum_order_ratio_fold_difference": (
                max_order_ratio_fold_difference
            ),
            "maximum_temperature_span_c": max_temperature_span_c,
            "maximum_relative_humidity_span_pct": (
                max_relative_humidity_span_pct
            ),
            "gate_specification_confirmed_before_unblinding": (
                gate_specification_confirmed
            ),
            "machine_verified_locked_protocol_supplied": locked_protocol_verified,
            "exact_locked_sample_size_and_allocation_requirement_met": (
                exact_locked_sample_size_and_allocation_met
            ),
            "power_analysis_confirmation_is_self_attested": False,
            "power_analysis_calculations_machine_verified": locked_protocol_verified,
            "power_analysis_inputs_validated_by_this_tool": False,
            "power_analysis_input_values_authenticated": False,
            "power_basis": "surrogate_power_only",
            "actual_bootstrap_gate_validated": False,
            "protocol_fingerprint_proves_chronology": False,
            "threshold_source": (
                "locked_protocol_plus_chronology_self_attestation"
                if gate_specification_confirmed and locked_protocol_verified
                else (
                    "chronology_self_attested_but_no_machine_verified_lock"
                    if gate_specification_confirmed
                    else "not_confirmed_prespecified"
                )
            ),
            "minimum_run_count_source": (
                "machine_verified_locked_power_protocol"
                if locked_protocol_verified
                else "no_machine_verified_locked_power_protocol"
            ),
            "criterion": (
                "experimental provenance; no unmodelled blank subtraction; "
                "prespecified thresholds and a machine-verified locked power protocol; "
                "exact locked scope/total/per-order counts; 10000..1000000 bootstrap "
                "resamples; sufficient independent runs and both "
                "order groups; balanced and consistent order effects; single device/"
                "protocol; bounded environment; all overall/order CI lower bounds "
                ">= minimum reduction"
            ),
            "independent_run_requirement_met": independent_run_requirement_met,
            "order_representation_requirement_met": order_representation_met,
            "order_balance_requirement_met": order_balance_met,
            "traceability_requirement_met": traceability_complete,
            "single_device_and_protocol_requirement_met": (
                single_device_and_protocol
            ),
            "measurement_context_requirement_met": measurement_context_complete,
            "environment_tolerance_requirement_met": environment_tolerance_met,
            "bootstrap_requirement_met": bootstrap_requirement_met,
            "overall_effect_requirement_met": effect_passed,
            "order_specific_effect_requirement_met": (
                order_effect_requirement_met
            ),
            "order_consistency_requirement_met": order_consistency_met,
            "monte_carlo_boundary_indeterminate": boundary_indeterminate,
            "observed_ci_lower_bound": reduction_ci_lower,
            "failure_reasons": gate_failure_reasons,
            "status": gate_status,
            "dataset_rule_passed": bool(gate_passed),
            "passed": bool(gate_passed),
            "passed_is_compatibility_alias_for": "dataset_rule_passed",
        },
        "validation_scope": {
            "data_provenance": data_provenance,
            "demonstration_only": synthetic_demonstration,
            "analysis_completed": True,
            "analysis_pipeline_validated": True,
            "analysis_pipeline_validated_is_compatibility_alias_for": (
                "analysis_completed"
            ),
            "pipeline_validation_meaning": (
                "CSV/schema checks and the deterministic analysis completed "
                "successfully"
            ),
            "performance_acceptance_gate_passed": bool(gate_passed),
            "performance_acceptance_gate_passed_is_compatibility_alias_for": (
                "prespecified_gate.dataset_rule_passed"
            ),
            "power_basis": "surrogate_power_only",
            "actual_bootstrap_gate_validated": False,
            "device_performance_validated": False,
            "gate_pass_is_device_validation": False,
            "eligible_for_dataset_rule_evaluation": bool(
                eligible_for_dataset_rule_evaluation
            ),
            "hardware_acceptance_eligible": bool(
                eligible_for_dataset_rule_evaluation
            ),
            "hardware_acceptance_eligible_is_compatibility_alias_for": (
                "eligible_for_dataset_rule_evaluation"
            ),
        },
        "caveats": caveats,
    }
    # Fail before JSON emission if an implementation change introduces NaN/Infinity.
    json.dumps(report, allow_nan=False)
    return report


def analyze_csv(
    csv_path: Path | str,
    *,
    blank_policy: str = BLANK_POLICY_NONE,
    minimum_reduction_fraction: float = DEFAULT_MINIMUM_REDUCTION_FRACTION,
    minimum_independent_runs: int = DEFAULT_MINIMUM_INDEPENDENT_RUNS,
    minimum_runs_per_order: int = DEFAULT_MINIMUM_RUNS_PER_ORDER,
    minimum_order_balance_ratio: float = DEFAULT_MINIMUM_ORDER_BALANCE_RATIO,
    max_order_ratio_fold_difference: float = (
        DEFAULT_MAX_ORDER_RATIO_FOLD_DIFFERENCE
    ),
    max_temperature_span_c: float = DEFAULT_MAX_TEMPERATURE_SPAN_C,
    max_relative_humidity_span_pct: float = (
        DEFAULT_MAX_RELATIVE_HUMIDITY_SPAN_PCT
    ),
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    gate_specification_confirmed: bool = False,
    locked_protocol: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Analyze one immutable byte snapshot and attach its SHA-256 digest."""

    path = Path(csv_path)
    csv_snapshot = path.read_bytes()
    trials = load_paired_trials(path, _snapshot_bytes=csv_snapshot)
    report = analyze_trials(
        trials,
        blank_policy=blank_policy,
        minimum_reduction_fraction=minimum_reduction_fraction,
        minimum_independent_runs=minimum_independent_runs,
        minimum_runs_per_order=minimum_runs_per_order,
        minimum_order_balance_ratio=minimum_order_balance_ratio,
        max_order_ratio_fold_difference=max_order_ratio_fold_difference,
        max_temperature_span_c=max_temperature_span_c,
        max_relative_humidity_span_pct=max_relative_humidity_span_pct,
        bootstrap_resamples=bootstrap_resamples,
        seed=seed,
        gate_specification_confirmed=gate_specification_confirmed,
        locked_protocol=locked_protocol,
    )
    report["input"] = {
        "csv_path": str(path),
        "sha256": hashlib.sha256(csv_snapshot).hexdigest(),
        "sha256_covers": "exact_bytes_parsed_by_this_analysis",
    }
    return report


def _fraction_argument(text: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number in [0, 1)") from error
    if not math.isfinite(value) or not 0.0 <= value < 1.0:
        raise argparse.ArgumentTypeError("must be finite and in [0, 1)")
    return value


def _positive_unit_interval_argument(text: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number in (0, 1]") from error
    if not math.isfinite(value) or not 0.0 < value <= 1.0:
        raise argparse.ArgumentTypeError("must be finite and in (0, 1]")
    return value


def _fold_argument(text: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a finite number >= 1") from error
    if not math.isfinite(value) or value < 1.0:
        raise argparse.ArgumentTypeError("must be a finite number >= 1")
    return value


def _nonnegative_float_argument(text: str) -> float:
    try:
        value = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a finite number >= 0") from error
    if not math.isfinite(value) or value < 0.0:
        raise argparse.ArgumentTypeError("must be a finite number >= 0")
    return value


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze randomized paired field-OFF/field-ON deposition counts and "
            "emit JSON."
        )
    )
    parser.add_argument("csv_path", type=Path, help="paired trial CSV")
    parser.add_argument(
        "--blank-policy",
        choices=BLANK_POLICIES,
        default=BLANK_POLICY_NONE,
        help="none, or subtract each condition's paired blank before log ratios",
    )
    parser.add_argument(
        "--minimum-reduction",
        type=_fraction_argument,
        default=DEFAULT_MINIMUM_REDUCTION_FRACTION,
        help=(
            "prespecified minimum reduction fraction; default: "
            f"{DEFAULT_MINIMUM_REDUCTION_FRACTION}"
        ),
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=DEFAULT_BOOTSTRAP_RESAMPLES,
        help=(
            "independent-run cluster resamples; allowed range "
            f"{MINIMUM_GATE_BOOTSTRAP_RESAMPLES}..{MAXIMUM_BOOTSTRAP_RESAMPLES}"
        ),
    )
    parser.add_argument(
        "--minimum-independent-runs",
        type=int,
        default=DEFAULT_MINIMUM_INDEPENDENT_RUNS,
        help=(
            "prespecified unique independent-run minimum; default: "
            f"{DEFAULT_MINIMUM_INDEPENDENT_RUNS}"
        ),
    )
    parser.add_argument(
        "--minimum-runs-per-order",
        type=int,
        default=DEFAULT_MINIMUM_RUNS_PER_ORDER,
        help=(
            "prespecified minimum independent runs in each randomized order; "
            f"default: {DEFAULT_MINIMUM_RUNS_PER_ORDER}"
        ),
    )
    parser.add_argument(
        "--minimum-order-balance-ratio",
        type=_positive_unit_interval_argument,
        default=DEFAULT_MINIMUM_ORDER_BALANCE_RATIO,
        help="prespecified min(smaller order n / larger order n); default: 0.5",
    )
    parser.add_argument(
        "--max-order-ratio-fold-difference",
        type=_fold_argument,
        default=DEFAULT_MAX_ORDER_RATIO_FOLD_DIFFERENCE,
        help="maximum allowed fold-difference between order-specific ratios; default: 1.5",
    )
    parser.add_argument(
        "--max-temperature-span-c",
        type=_nonnegative_float_argument,
        default=DEFAULT_MAX_TEMPERATURE_SPAN_C,
        help="prespecified maximum within-analysis temperature span; default: 1 C",
    )
    parser.add_argument(
        "--max-relative-humidity-span-pct",
        type=_nonnegative_float_argument,
        default=DEFAULT_MAX_RELATIVE_HUMIDITY_SPAN_PCT,
        help=(
            "prespecified maximum within-analysis relative-humidity span; "
            "default: 5 percentage points"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_BOOTSTRAP_SEED,
        help="non-negative deterministic bootstrap seed",
    )
    parser.add_argument(
        "--confirm-prespecified-gate",
        action="store_true",
        help=(
            "self-attest that the locked protocol, exact experimental scope and "
            "sample allocation, stopping and replacement rules, gate options, and "
            "seed were fixed before any outcome access; this does not prove chronology"
        ),
    )
    parser.add_argument(
        "--locked-protocol-json",
        type=Path,
        help=(
            "machine-verify a deposition power-protocol JSON and require its protocol_id, "
            "analysis_gate, experimental scope, and exact total/per-order run counts "
            "to match"
        ),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="return zero after a valid report even when the gate does not pass",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="also write the JSON report to this path",
    )
    return parser


def _paths_refer_to_same_file(first: Path, second: Path) -> bool:
    try:
        if first.resolve(strict=False) == second.resolve(strict=False):
            return True
        return first.samefile(second)
    except FileNotFoundError:
        return False
    except (OSError, RuntimeError):
        # Unknown aliasing, including a symlink cycle, must fail closed.
        return True


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace ``path`` using a temporary file in the same directory."""

    # ``resolve`` follows a final symlink and could overwrite its unrelated
    # target.  ``abspath`` is lexical: os.replace replaces the symlink entry.
    destination = Path(os.path.abspath(os.fspath(path)))
    destination.parent.mkdir(parents=False, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, destination)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        if args.output_json is not None and _paths_refer_to_same_file(
            args.csv_path, args.output_json
        ):
            raise ValueError("input CSV and JSON output must be different files")
        if (
            args.output_json is not None
            and args.locked_protocol_json is not None
            and _paths_refer_to_same_file(
                args.locked_protocol_json, args.output_json
            )
        ):
            raise ValueError(
                "locked protocol JSON and JSON output must be different files"
            )
        locked_protocol = (
            deposition_power.load_locked_protocol(args.locked_protocol_json)
            if args.locked_protocol_json is not None
            else None
        )
        report = analyze_csv(
            args.csv_path,
            blank_policy=args.blank_policy,
            minimum_reduction_fraction=args.minimum_reduction,
            minimum_independent_runs=args.minimum_independent_runs,
            minimum_runs_per_order=args.minimum_runs_per_order,
            minimum_order_balance_ratio=args.minimum_order_balance_ratio,
            max_order_ratio_fold_difference=(
                args.max_order_ratio_fold_difference
            ),
            max_temperature_span_c=args.max_temperature_span_c,
            max_relative_humidity_span_pct=(
                args.max_relative_humidity_span_pct
            ),
            bootstrap_resamples=args.bootstrap_resamples,
            seed=args.seed,
            gate_specification_confirmed=args.confirm_prespecified_gate,
            locked_protocol=locked_protocol,
        )
        document = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
        if args.output_json is not None:
            _atomic_write_text(args.output_json, document + "\n")
        print(document)
    except (OSError, csv.Error, TypeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                    "device_performance_validated": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR

    if args.report_only or report["prespecified_gate"]["dataset_rule_passed"]:
        return EXIT_OK
    return EXIT_GATE_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
