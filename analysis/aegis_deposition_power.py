#!/usr/bin/env python3
"""Prospective sample-size planning for paired deposition experiments.

The independent endpoint is one value per independent run::

    Y_i = mean_j(log(field_on_corrected / field_off_corrected))

This planner uses a known-SD Normal approximation.  Its Monte Carlo check is a
surrogate for, not a validation of, the analyzer's percentile-bootstrap gate.
It jointly requires an overall upper bound, both randomized-order upper bounds,
and the prespecified order-consistency bound to pass.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping, Optional, Sequence

import numpy as np


SCHEMA_VERSION = 3
DOCUMENT_TYPE = "aegis_deposition_power_protocol"
PLANNER_ALGORITHM_ID = "known_sd_joint_z_surrogate_v2"
RNG_ALGORITHM_ID = "sha256_counter_domain_box_muller_u52_round12_v1"
FINGERPRINT_ALGORITHM = "sha256"
FINGERPRINT_CANONICALIZATION = (
    "RFC8785-inspired sorted-key compact UTF-8 JSON excluding "
    "protocol_fingerprint"
)
CURRENT_ANALYZER_TWO_SIDED_ALPHA = 0.05
MINIMUM_MC_RESAMPLES = 10_000
MAXIMUM_MC_RESAMPLES = 1_000_000
MINIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES = 10_000
MAXIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES = 1_000_000
MAXIMUM_SEED = (1 << 64) - 1
DEFAULT_MC_SEARCH_SEED = 20_260_821
DEFAULT_MC_VALIDATION_SEED = 20_260_822
DEFAULT_ANALYSIS_BOOTSTRAP_SEED = 20_260_820
MINIMUM_PILOT_INDEPENDENT_RUNS = 12
MINIMUM_PILOT_SD_MULTIPLIER = 1.25


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _integer(name: str, value: Any, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _nonempty_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _strict_boolean(name: str, value: Any) -> bool:
    """Return a boolean without accepting Python's integer/bool coercion."""

    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _seed(name: str, value: Any) -> int:
    result = _integer(name, value, 0)
    if result > MAXIMUM_SEED:
        raise ValueError(f"{name} must be <= {MAXIMUM_SEED}")
    return result


def _open_unit_interval_from_uint64(value: int) -> float:
    """Map an unsigned 64-bit integer to an exactly open binary64 midpoint."""

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= MAXIMUM_SEED
    ):
        raise ValueError("value must be an unsigned 64-bit integer")
    return ((value >> 12) + 0.5) / float(1 << 52)


def _deterministic_standard_normals(
    seed: int,
    replicates: int,
    *,
    stream_domain: str,
) -> np.ndarray:
    """Return versioned, domain-separated deterministic N(0,1) pairs.

    SHA-256 expands the explicit domain, seed, and counter into two open-
    interval 52-bit midpoint uniforms per replicate.  Box--Muller converts them to a
    pair of Normals; rounding to 12 decimal places is part of
    ``RNG_ALGORITHM_ID`` and limits cross-libm drift.  Domain separation keeps
    search and final validation from being shifted views of one counter stream.
    """

    seed = _seed("seed", seed)
    replicates = _integer("replicates", replicates, 1)
    stream_domain = _nonempty_text("stream_domain", stream_domain)
    domain_bytes = stream_domain.encode("utf-8")
    if len(domain_bytes) > 2**32 - 1:
        raise ValueError("stream_domain is too long")
    prefix = (
        RNG_ALGORITHM_ID.encode("ascii")
        + b"\x00"
        + len(domain_bytes).to_bytes(4, "big")
        + domain_bytes
        + seed.to_bytes(8, "big")
    )
    output = np.empty((replicates, 2), dtype=float)

    for index in range(replicates):
        digest = hashlib.sha256(prefix + index.to_bytes(8, "big")).digest()
        first_uniform = _open_unit_interval_from_uint64(
            int.from_bytes(digest[0:8], "big")
        )
        second_uniform = _open_unit_interval_from_uint64(
            int.from_bytes(digest[8:16], "big")
        )
        radius = math.sqrt(-2.0 * math.log(first_uniform))
        angle = 2.0 * math.pi * second_uniform
        output[index, 0] = round(radius * math.cos(angle), 12)
        output[index, 1] = round(radius * math.sin(angle), 12)
    return output


def _normal_screening_runs_per_order(
    design_sd: float,
    log_margin_gap: float,
    critical_z: float,
    power_z: float,
    minimum_floor: int,
) -> int:
    continuous = ((critical_z + power_z) * design_sd / log_margin_gap) ** 2
    if not math.isfinite(continuous):
        raise ValueError("calculated sample size is not finite")
    return max(minimum_floor, int(math.ceil(continuous)))


def _wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("invalid binomial counts")
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    half = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def _joint_surrogate_result(
    standard_normals: np.ndarray,
    runs_per_order: int,
    *,
    alternative_log_ratio: float,
    null_log_ratio: float,
    design_sd: float,
    critical_z: float,
    max_order_log_difference: float,
) -> dict[str, Any]:
    standard_error = design_sd / math.sqrt(runs_per_order)
    order_means = alternative_log_ratio + standard_error * standard_normals
    order_upper = order_means + critical_z * standard_error
    pooled_mean = np.mean(order_means, axis=1)
    pooled_upper = pooled_mean + critical_z * design_sd / math.sqrt(2 * runs_per_order)
    successes_vector = (
        (pooled_upper < null_log_ratio)
        & (order_upper[:, 0] < null_log_ratio)
        & (order_upper[:, 1] < null_log_ratio)
        & (np.abs(order_means[:, 0] - order_means[:, 1]) <= max_order_log_difference)
    )
    successes = int(np.count_nonzero(successes_vector))
    trials = int(standard_normals.shape[0])
    estimate = successes / trials
    lower, upper = _wilson_interval(successes, trials)
    return {
        "runs_per_order": runs_per_order,
        "total_independent_runs": 2 * runs_per_order,
        "successes": successes,
        "replicates": trials,
        "estimated_joint_power": estimate,
        "monte_carlo_standard_error": math.sqrt(estimate * (1.0 - estimate) / trials),
        "wilson_95_percent_ci": [lower, upper],
        "wilson_95_percent_lower": lower,
    }


def _find_recommended_runs(
    standard_normals: np.ndarray,
    initial_runs_per_order: int,
    minimum_floor: int,
    target_joint_power: float,
    simulation_options: Mapping[str, float],
) -> dict[str, Any]:
    maximum_lower, _ = _wilson_interval(len(standard_normals), len(standard_normals))
    if maximum_lower < target_joint_power:
        raise ValueError(
            "MC search resamples are too few for their Wilson lower bound ever "
            "to reach target_joint_power"
        )

    def evaluate(runs_per_order: int) -> dict[str, Any]:
        return _joint_surrogate_result(
            standard_normals,
            runs_per_order,
            alternative_log_ratio=simulation_options["alternative_log_ratio"],
            null_log_ratio=simulation_options["null_log_ratio"],
            design_sd=simulation_options["design_sd"],
            critical_z=simulation_options["critical_z"],
            max_order_log_difference=simulation_options["max_order_log_difference"],
        )

    screening_floor = max(minimum_floor, initial_runs_per_order)
    high = screening_floor
    high_result = evaluate(high)
    while high_result["wilson_95_percent_lower"] < target_joint_power:
        high *= 2
        if high > 1_000_000_000:
            raise ValueError("required independent-run count exceeds supported search range")
        high_result = evaluate(high)

    # The analytic per-order screening result is a conservative lower bound,
    # not merely a search starting point.  MC may increase but never reduce it.
    low = screening_floor - 1
    while high - low > 1:
        middle = (low + high) // 2
        middle_result = evaluate(middle)
        if middle_result["wilson_95_percent_lower"] >= target_joint_power:
            high = middle
            high_result = middle_result
        else:
            low = middle
    return high_result


def _canonical_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(document))
    payload.pop("protocol_fingerprint", None)
    return payload


def _canonical_protocol_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _canonical_payload(document),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_protocol_sha256(document: Mapping[str, Any]) -> str:
    """Return the canonical SHA-256 of a protocol, excluding its fingerprint."""

    if not isinstance(document, Mapping):
        raise TypeError("document must be a mapping")
    return hashlib.sha256(_canonical_protocol_bytes(document)).hexdigest()


def _attach_fingerprint(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result["protocol_fingerprint"] = {
        "algorithm": FINGERPRINT_ALGORITHM,
        "canonicalization": FINGERPRINT_CANONICALIZATION,
        "canonical_sha256": canonical_protocol_sha256(result),
        "proves": "content_identity_only",
        "does_not_prove": [
            "authorship_or_identity",
            "creation_time_or_pre_registration_chronology",
            "protocol_execution",
            "hardware_performance",
        ],
    }
    return result


def plan_power(
    protocol_id: str,
    *,
    example_only: bool = False,
    device_id: str,
    particle_nm: float,
    gas: str,
    flow_slm: float,
    exposure_s: float,
    sampled_area_cm2: float,
    measurement_method_id: str,
    exclusion_policy_id: str,
    stopping_rule_id: str,
    replacement_policy_id: str,
    two_sided_alpha: float = 0.05,
    minimum_reduction_fraction: float = 0.30,
    anticipated_reduction_fraction: float = 0.45,
    target_joint_power: float = 0.80,
    pilot_log_ratio_sd: Optional[float] = None,
    pilot_independent_run_count: Optional[int] = None,
    conservative_assumed_log_ratio_sd: Optional[float] = 0.35,
    pilot_sd_design_multiplier: float = 1.25,
    minimum_runs_per_order_floor: int = 3,
    max_order_ratio_fold_difference: float = 1.50,
    mc_search_resamples: int = 100_000,
    mc_search_seed: int = DEFAULT_MC_SEARCH_SEED,
    mc_validation_resamples: int = 100_000,
    mc_validation_seed: int = DEFAULT_MC_VALIDATION_SEED,
    analysis_blank_policy: str = "none",
    minimum_order_balance_ratio: float = 0.50,
    max_temperature_span_c: float = 1.0,
    max_relative_humidity_span_pct: float = 5.0,
    analysis_bootstrap_resamples: int = MINIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES,
    analysis_bootstrap_seed: int = DEFAULT_ANALYSIS_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Build and fingerprint a deterministic prospective protocol document."""

    protocol_id = _nonempty_text("protocol_id", protocol_id)
    example_only = _strict_boolean("example_only", example_only)
    device_id = _nonempty_text("device_id", device_id)
    gas = _nonempty_text("gas", gas)
    measurement_method_id = _nonempty_text(
        "measurement_method_id", measurement_method_id
    )
    exclusion_policy_id = _nonempty_text(
        "exclusion_policy_id", exclusion_policy_id
    )
    stopping_rule_id = _nonempty_text("stopping_rule_id", stopping_rule_id)
    replacement_policy_id = _nonempty_text(
        "replacement_policy_id", replacement_policy_id
    )
    particle_nm = _finite_number("particle_nm", particle_nm)
    flow_slm = _finite_number("flow_slm", flow_slm)
    exposure_s = _finite_number("exposure_s", exposure_s)
    sampled_area_cm2 = _finite_number("sampled_area_cm2", sampled_area_cm2)
    alpha = _finite_number("two_sided_alpha", two_sided_alpha)
    minimum_reduction = _finite_number(
        "minimum_reduction_fraction", minimum_reduction_fraction
    )
    anticipated_reduction = _finite_number(
        "anticipated_reduction_fraction", anticipated_reduction_fraction
    )
    power = _finite_number("target_joint_power", target_joint_power)
    multiplier = _finite_number(
        "pilot_sd_design_multiplier", pilot_sd_design_multiplier
    )
    max_fold = _finite_number(
        "max_order_ratio_fold_difference", max_order_ratio_fold_difference
    )
    balance = _finite_number(
        "minimum_order_balance_ratio", minimum_order_balance_ratio
    )
    temperature_span = _finite_number(
        "max_temperature_span_c", max_temperature_span_c
    )
    humidity_span = _finite_number(
        "max_relative_humidity_span_pct", max_relative_humidity_span_pct
    )
    floor = _integer(
        "minimum_runs_per_order_floor", minimum_runs_per_order_floor, 2
    )
    mc_search_resamples = _integer(
        "mc_search_resamples", mc_search_resamples, MINIMUM_MC_RESAMPLES
    )
    mc_validation_resamples = _integer(
        "mc_validation_resamples",
        mc_validation_resamples,
        MINIMUM_MC_RESAMPLES,
    )
    if (
        mc_search_resamples > MAXIMUM_MC_RESAMPLES
        or mc_validation_resamples > MAXIMUM_MC_RESAMPLES
    ):
        raise ValueError(f"MC resamples must be <= {MAXIMUM_MC_RESAMPLES}")
    mc_search_seed = _seed("mc_search_seed", mc_search_seed)
    mc_validation_seed = _seed("mc_validation_seed", mc_validation_seed)
    if mc_search_seed == mc_validation_seed:
        raise ValueError("MC search and validation seeds must be different")
    analysis_bootstrap_resamples = _integer(
        "analysis_bootstrap_resamples",
        analysis_bootstrap_resamples,
        MINIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES,
    )
    if analysis_bootstrap_resamples > MAXIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES:
        raise ValueError(
            "analysis_bootstrap_resamples must be <= "
            f"{MAXIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES}"
        )
    analysis_bootstrap_seed = _seed(
        "analysis_bootstrap_seed", analysis_bootstrap_seed
    )

    if particle_nm <= 0.0:
        raise ValueError("particle_nm must be > 0")
    if flow_slm < 0.0:
        raise ValueError("flow_slm must be >= 0")
    if exposure_s <= 0.0 or sampled_area_cm2 <= 0.0:
        raise ValueError("exposure_s and sampled_area_cm2 must be > 0")

    if not 0.0 < alpha < 1.0:
        raise ValueError("two_sided_alpha must be between 0 and 1")
    if not 0.0 <= minimum_reduction < anticipated_reduction < 1.0:
        raise ValueError(
            "reductions must satisfy 0 <= minimum_reduction_fraction < "
            "anticipated_reduction_fraction < 1"
        )
    if not 0.5 < power < 1.0:
        raise ValueError("target_joint_power must be between 0.5 and 1")
    if multiplier <= 0.0:
        raise ValueError("pilot_sd_design_multiplier must be > 0")
    if max_fold < 1.0:
        raise ValueError("max_order_ratio_fold_difference must be >= 1")
    if not 0.0 < balance <= 1.0:
        raise ValueError("minimum_order_balance_ratio must be in (0, 1]")
    if temperature_span < 0.0 or humidity_span < 0.0:
        raise ValueError("environment spans must be >= 0")
    if analysis_blank_policy != "none":
        raise ValueError(
            "only blank_policy='none' supports acceptance planning; "
            "paired_subtract remains diagnostic-only"
        )

    has_pilot = pilot_log_ratio_sd is not None
    has_assumed = conservative_assumed_log_ratio_sd is not None
    if has_pilot == has_assumed:
        raise ValueError(
            "provide exactly one of pilot_log_ratio_sd or "
            "conservative_assumed_log_ratio_sd"
        )
    if has_pilot:
        if multiplier < MINIMUM_PILOT_SD_MULTIPLIER:
            raise ValueError(
                "pilot_sd_design_multiplier must be >= "
                f"{MINIMUM_PILOT_SD_MULTIPLIER} for a lock-eligible pilot plan"
            )
        pilot_sd = _finite_number("pilot_log_ratio_sd", pilot_log_ratio_sd)
        if pilot_sd <= 0.0:
            raise ValueError("pilot_log_ratio_sd must be > 0")
        pilot_count = _integer(
            "pilot_independent_run_count",
            pilot_independent_run_count,
            MINIMUM_PILOT_INDEPENDENT_RUNS,
        )
        design_sd = pilot_sd * multiplier
        sd_source = {
            "kind": "pilot_independent_run_log_ratio_sd",
            "reported_sd": pilot_sd,
            "pilot_independent_run_count": pilot_count,
            "prespecified_design_multiplier": multiplier,
            "design_sd": design_sd,
            "warning": (
                "The multiplier is a conservative scenario, not a formal "
                "upper confidence bound or assurance calculation."
            ),
        }
    else:
        if pilot_independent_run_count is not None:
            raise ValueError(
                "pilot_independent_run_count is only valid with pilot_log_ratio_sd"
            )
        assumed_sd = _finite_number(
            "conservative_assumed_log_ratio_sd", conservative_assumed_log_ratio_sd
        )
        if assumed_sd <= 0.0:
            raise ValueError("conservative_assumed_log_ratio_sd must be > 0")
        design_sd = assumed_sd
        sd_source = {
            "kind": "conservative_assumed_log_ratio_sd",
            "reported_sd": assumed_sd,
            "pilot_independent_run_count": None,
            "prespecified_design_multiplier": None,
            "design_sd": design_sd,
            "warning": "The assumed SD must be justified before data collection.",
        }

    null_log_ratio = math.log1p(-minimum_reduction)
    alternative_log_ratio = math.log1p(-anticipated_reduction)
    log_margin_gap = null_log_ratio - alternative_log_ratio
    one_sided_tail_alpha = alpha / 2.0
    critical_z = NormalDist().inv_cdf(1.0 - one_sided_tail_alpha)
    per_order_screening_power = 1.0 - (1.0 - power) / 2.0
    power_z = NormalDist().inv_cdf(per_order_screening_power)
    initial_runs = _normal_screening_runs_per_order(
        design_sd, log_margin_gap, critical_z, power_z, floor
    )

    search_normals = _deterministic_standard_normals(
        mc_search_seed,
        mc_search_resamples,
        stream_domain="sample_size_search",
    )
    validation_normals = _deterministic_standard_normals(
        mc_validation_seed,
        mc_validation_resamples,
        stream_domain="independent_final_validation",
    )
    simulation_options = {
        "alternative_log_ratio": alternative_log_ratio,
        "null_log_ratio": null_log_ratio,
        "design_sd": design_sd,
        "critical_z": critical_z,
        "max_order_log_difference": math.log(max_fold),
    }
    recommendation = _find_recommended_runs(
        search_normals,
        initial_runs,
        floor,
        power,
        simulation_options,
    )
    validation_result = _joint_surrogate_result(
        validation_normals,
        recommendation["runs_per_order"],
        alternative_log_ratio=alternative_log_ratio,
        null_log_ratio=null_log_ratio,
        design_sd=design_sd,
        critical_z=critical_z,
        max_order_log_difference=math.log(max_fold),
    )

    sensitivity = []
    for factor in (1.0, 1.25, 1.5):
        scenario_sd = design_sd * factor
        scenario_runs = _normal_screening_runs_per_order(
            scenario_sd, log_margin_gap, critical_z, power_z, floor
        )
        scenario_recommendation = _find_recommended_runs(
            search_normals,
            scenario_runs,
            floor,
            power,
            {
                **simulation_options,
                "design_sd": scenario_sd,
            },
        )
        scenario_validation = _joint_surrogate_result(
            validation_normals,
            scenario_recommendation["runs_per_order"],
            alternative_log_ratio=alternative_log_ratio,
            null_log_ratio=null_log_ratio,
            design_sd=scenario_sd,
            critical_z=critical_z,
            max_order_log_difference=math.log(max_fold),
        )
        sensitivity.append(
            {
                "design_sd_factor": factor,
                "log_ratio_sd": scenario_sd,
                "normal_screening_runs_per_order": scenario_runs,
                "normal_screening_total_independent_runs": 2 * scenario_runs,
                "joint_surrogate_recommended_runs_per_order": (
                    scenario_recommendation["runs_per_order"]
                ),
                "joint_surrogate_recommended_total_independent_runs": (
                    scenario_recommendation["total_independent_runs"]
                ),
                "joint_surrogate_wilson_95_percent_lower": (
                    scenario_validation["wilson_95_percent_lower"]
                ),
                "independent_validation_result": scenario_validation,
            }
        )

    analyzer_compatible = math.isclose(
        alpha, CURRENT_ANALYZER_TWO_SIDED_ALPHA, rel_tol=0.0, abs_tol=1e-15
    )
    independent_validation_power_met = (
        validation_result["wilson_95_percent_lower"] >= power
    )
    lock_eligible = analyzer_compatible and independent_validation_power_met
    execution_eligible = lock_eligible and not example_only
    recommended_per_order = recommendation["runs_per_order"]
    document = {
        "schema_version": SCHEMA_VERSION,
        "document_type": DOCUMENT_TYPE,
        "algorithm": {
            "planner_algorithm_id": PLANNER_ALGORITHM_ID,
            "rng_algorithm_id": RNG_ALGORITHM_ID,
        },
        "planning_inputs": {
            "device_id": device_id,
            "particle_nm": particle_nm,
            "gas": gas,
            "flow_slm": flow_slm,
            "exposure_s": exposure_s,
            "sampled_area_cm2": sampled_area_cm2,
            "measurement_method_id": measurement_method_id,
            "exclusion_policy_id": exclusion_policy_id,
            "stopping_rule_id": stopping_rule_id,
            "replacement_policy_id": replacement_policy_id,
            "two_sided_alpha": alpha,
            "minimum_reduction_fraction": minimum_reduction,
            "anticipated_reduction_fraction": anticipated_reduction,
            "target_joint_power": power,
            "pilot_log_ratio_sd": pilot_sd if has_pilot else None,
            "pilot_independent_run_count": pilot_count if has_pilot else None,
            "conservative_assumed_log_ratio_sd": (
                None if has_pilot else assumed_sd
            ),
            "pilot_sd_design_multiplier": multiplier,
            "minimum_runs_per_order_floor": floor,
            "max_order_ratio_fold_difference": max_fold,
            "mc_search_resamples": mc_search_resamples,
            "mc_search_seed": mc_search_seed,
            "mc_validation_resamples": mc_validation_resamples,
            "mc_validation_seed": mc_validation_seed,
            "analysis_blank_policy": analysis_blank_policy,
            "minimum_order_balance_ratio": balance,
            "max_temperature_span_c": temperature_span,
            "max_relative_humidity_span_pct": humidity_span,
            "analysis_bootstrap_resamples": analysis_bootstrap_resamples,
            "analysis_bootstrap_seed": analysis_bootstrap_seed,
        },
        "protocol": {
            "protocol_id": protocol_id,
            "example_only": example_only,
            "execution_eligible": execution_eligible,
            "execution_eligibility_rule": "lock_eligible_and_not_example_only",
            "lock_eligibility_meaning": (
                "deterministic_verifier_compatible_not_execution_authorization"
            ),
            "prospective_only": True,
            "hardware_performance_validated": False,
            "power_basis": "surrogate_power_only",
            "actual_bootstrap_gate_validated": False,
            "current_analyzer_gate_compatible": analyzer_compatible,
            "independent_validation_power_requirement_met": (
                independent_validation_power_met
            ),
            "lock_eligible": lock_eligible,
            "experimental_scope": {
                "device_id": device_id,
                "particle_nm": particle_nm,
                "gas": gas,
                "flow_slm": flow_slm,
                "exposure_s": exposure_s,
                "sampled_area_cm2": sampled_area_cm2,
                "measurement_method_id": measurement_method_id,
                "exclusion_policy_id": exclusion_policy_id,
                "stopping_rule_id": stopping_rule_id,
                "replacement_policy_id": replacement_policy_id,
            },
        },
        "analysis_gate": {
            "blank_policy": analysis_blank_policy,
            "minimum_reduction_fraction": minimum_reduction,
            "minimum_independent_runs": 2 * recommended_per_order,
            "minimum_runs_per_order": recommended_per_order,
            "minimum_order_balance_ratio": balance,
            "max_order_ratio_fold_difference": max_fold,
            "max_temperature_span_c": temperature_span,
            "max_relative_humidity_span_pct": humidity_span,
            "bootstrap_resamples": analysis_bootstrap_resamples,
            "bootstrap_seed": analysis_bootstrap_seed,
        },
        "power_plan": {
            "power_basis": "surrogate_power_only",
            "actual_bootstrap_gate_validated": False,
            "endpoint": {
                "independent_unit": "independent_run_id",
                "definition": "Y_i = mean_j(log(field_on_corrected / field_off_corrected))",
                "rows_are_not_independent_when_they_share_independent_run_id": True,
            },
            "hypotheses": {
                "reduction_definition": "R = 1 - exp(mean(Y_i))",
                "null": (
                    "H0: mean(Y_i) >= log(1 - minimum_reduction_fraction), "
                    "equivalently R <= minimum_reduction_fraction"
                ),
                "alternative": (
                    "H1: mean(Y_i) < log(1 - minimum_reduction_fraction), "
                    "equivalently R > minimum_reduction_fraction"
                ),
                "null_boundary_log_ratio": null_log_ratio,
                "minimum_reduction_fraction": minimum_reduction,
                "anticipated_alternative_log_ratio": alternative_log_ratio,
                "anticipated_reduction_fraction": anticipated_reduction,
                "log_margin_gap": log_margin_gap,
                "two_sided_alpha": alpha,
                "one_sided_upper_tail_alpha": one_sided_tail_alpha,
                "compatibility_note": (
                    "alpha/2 matches the upper endpoint of the analyzer's "
                    "central two-sided confidence interval"
                ),
            },
            "assumptions": {
                "sd_source": sd_source,
                "target_joint_power": power,
                "planned_randomized_orders": ["off_then_on", "on_then_off"],
                "allocation": "equal independent-run counts in both orders",
                "normal_independent_run_endpoint": True,
                "known_design_sd_surrogate": True,
                "order_distributions_assumed_equal_under_planning_alternative": True,
                "minimum_runs_per_order_floor": floor,
                "threshold_is_user_prespecified": True,
                "recommended_run_counts_are_power_plan_outputs": True,
            },
            "formula": {
                "description": (
                    "Normal known-SD screening approximation per order: "
                    "ceil(((z_(1-alpha/2)+z_(per-order power))*sigma/(mu0-mu1))^2); "
                    "per-order screening power = 1-(1-target joint power)/2."
                ),
                "source_description": (
                    "Standard one-sample Normal mean test approximation; used only "
                    "as an initial sample-size bound, not as an exact bootstrap-gate calculation."
                ),
                "critical_z": critical_z,
                "per_order_screening_power": per_order_screening_power,
                "power_z": power_z,
                "normal_screening_runs_per_order": initial_runs,
                "normal_screening_total_independent_runs": 2 * initial_runs,
            },
            "joint_gate_simulation": {
                "method": "seeded_known_sd_normal_z_bound_surrogate",
                "rng_algorithm_id": RNG_ALGORITHM_ID,
                "joint_success_rule": (
                    "pooled and both order-specific known-SD z upper bounds are below "
                    "the null log-ratio boundary, and the absolute order mean difference "
                    "does not exceed log(max_order_ratio_fold_difference)"
                ),
                "target_joint_power": power,
                "max_order_ratio_fold_difference": max_fold,
                "max_order_log_difference": math.log(max_fold),
                "recommendation_requires_wilson_lower_at_least_target": True,
                "search": {
                    "stream_domain": "sample_size_search",
                    "seed": mc_search_seed,
                    "replicates": mc_search_resamples,
                    "result": recommendation,
                    "used_for_run_count_selection": True,
                },
                "independent_validation": {
                    "stream_domain": "independent_final_validation",
                    "seed": mc_validation_seed,
                    "replicates": mc_validation_resamples,
                    "result": validation_result,
                    "used_for_run_count_selection": False,
                    "wilson_lower_requirement_met": (
                        independent_validation_power_met
                    ),
                },
                "result": validation_result,
                "wilson_interval_is_independent_of_sample_size_search": True,
                "validated_against_actual_bootstrap_gate": False,
                "exact_or_full_analyzer_gate_simulation": False,
                "limitation": (
                    "The analyzer uses percentile bootstrap intervals and additional data-quality "
                    "checks; actual locked-protocol operating characteristics "
                    "require separate validation."
                ),
            },
            "sensitivity_scenarios": sensitivity,
            "recommended_independent_runs": {
                "total": 2 * recommended_per_order,
                "per_order": recommended_per_order,
                "off_then_on": recommended_per_order,
                "on_then_off": recommended_per_order,
                "balanced_total_is_even": True,
                "counts_are_independent_runs_not_csv_rows": True,
                "acceptance_requires_exact_counts": True,
                "unplanned_continuation_is_gate_ineligible": True,
            },
            "limitations": [
                "Prospective planning output is not experimental evidence.",
                *(
                    [
                        "This repository example is a software-reproducibility "
                        "fixture, is not a hardware record, and is ineligible for "
                        "deposition acceptance analysis."
                    ]
                    if example_only
                    else []
                ),
                "Known-SD Normal simulation does not validate the actual "
                "percentile-bootstrap gate.",
                "Pilot or assumed SD uncertainty is not fully modeled.",
                "The reported final Wilson interval uses a validation stream "
                "independent of the run-count search, but remains a Monte Carlo "
                "uncertainty diagnostic for the z-surrogate only.",
                "Scope and rule identifiers are content-bound strings; their "
                "authorship, semantics, chronology, and execution require an "
                "external signed protocol registry and deviation log.",
                "The fingerprint proves content identity only; use an external "
                "signed, timestamped registry for chronology.",
            ],
        },
    }
    return _attach_fingerprint(document)


def build_power_protocol(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Public alias for :func:`plan_power`."""

    return plan_power(*args, **kwargs)


def plan_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Build a plan from the documented JSON configuration schema."""

    if not isinstance(config, Mapping):
        raise TypeError("config must be a JSON object")
    expected_config_keys = {"protocol", "planning_inputs", "analysis_gate"}
    if set(config) != expected_config_keys:
        raise ValueError(
            "config fields must be exactly: analysis_gate, planning_inputs, protocol"
        )
    protocol = config.get("protocol")
    planning = config.get("planning_inputs")
    gate = config.get("analysis_gate", {})
    if not isinstance(protocol, Mapping) or not isinstance(planning, Mapping):
        raise ValueError("config requires object fields 'protocol' and 'planning_inputs'")
    if not isinstance(gate, Mapping):
        raise ValueError("analysis_gate must be an object")
    if set(protocol) != {"protocol_id", "example_only"}:
        raise ValueError(
            "config protocol must contain exactly example_only and protocol_id"
        )
    example_only = _strict_boolean(
        "protocol.example_only", protocol.get("example_only")
    )
    kwargs = dict(planning)
    translations = {
        "blank_policy": "analysis_blank_policy",
        "bootstrap_resamples": "analysis_bootstrap_resamples",
        "bootstrap_seed": "analysis_bootstrap_seed",
    }
    allowed_gate_keys = set(translations).union(
        {
            "minimum_order_balance_ratio",
            "max_temperature_span_c",
            "max_relative_humidity_span_pct",
            "max_order_ratio_fold_difference",
        }
    )
    unexpected_gate_keys = sorted(set(gate).difference(allowed_gate_keys))
    if unexpected_gate_keys:
        raise ValueError(
            "unsupported or derived analysis_gate config field(s): "
            + ", ".join(unexpected_gate_keys)
        )
    for source, destination in translations.items():
        if source in gate:
            if destination in kwargs and kwargs[destination] != gate[source]:
                raise ValueError(
                    f"conflicting {source} values in planning_inputs and analysis_gate"
                )
            kwargs[destination] = gate[source]
    for key in (
        "minimum_order_balance_ratio",
        "max_temperature_span_c",
        "max_relative_humidity_span_pct",
        "max_order_ratio_fold_difference",
    ):
        if key in gate:
            if key in kwargs and kwargs[key] != gate[key]:
                raise ValueError(
                    f"conflicting {key} values in planning_inputs and analysis_gate"
                )
            kwargs[key] = gate[key]
    return plan_power(
        protocol.get("protocol_id"), example_only=example_only, **kwargs
    )


def verify_locked_protocol(document: dict[str, Any]) -> dict[str, Any]:
    """Verify identity and reproduce the complete deterministic power plan.

    SHA-256 is only an integrity check: it is public and can be recalculated by
    anyone.  Semantic verification therefore reruns :func:`plan_power` from
    the locked canonical inputs and requires byte-identical canonical payloads.
    """

    if not isinstance(document, dict):
        raise TypeError("locked protocol must be a dictionary")

    required_top_level = {
        "schema_version",
        "document_type",
        "algorithm",
        "planning_inputs",
        "protocol",
        "analysis_gate",
        "power_plan",
        "protocol_fingerprint",
    }
    if set(document) != required_top_level:
        missing = sorted(required_top_level.difference(document))
        unexpected = sorted(set(document).difference(required_top_level))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise ValueError("invalid locked protocol fields: " + "; ".join(details))
    if (
        document["schema_version"] != SCHEMA_VERSION
        or document["document_type"] != DOCUMENT_TYPE
    ):
        raise ValueError("unsupported locked protocol schema or document type")

    protocol = document["protocol"]
    algorithm = document["algorithm"]
    planning_inputs = document["planning_inputs"]
    fingerprint = document["protocol_fingerprint"]
    for name, value in (
        ("algorithm", algorithm),
        ("protocol", protocol),
        ("planning_inputs", planning_inputs),
        ("analysis_gate", document["analysis_gate"]),
        ("power_plan", document["power_plan"]),
        ("protocol_fingerprint", fingerprint),
    ):
        if not isinstance(value, dict):
            raise ValueError(f"{name} must be an object")

    if algorithm != {
        "planner_algorithm_id": PLANNER_ALGORITHM_ID,
        "rng_algorithm_id": RNG_ALGORITHM_ID,
    }:
        raise ValueError("unsupported planner or RNG algorithm identifier")

    expected_planning_input_keys = {
        "device_id",
        "particle_nm",
        "gas",
        "flow_slm",
        "exposure_s",
        "sampled_area_cm2",
        "measurement_method_id",
        "exclusion_policy_id",
        "stopping_rule_id",
        "replacement_policy_id",
        "two_sided_alpha",
        "minimum_reduction_fraction",
        "anticipated_reduction_fraction",
        "target_joint_power",
        "pilot_log_ratio_sd",
        "pilot_independent_run_count",
        "conservative_assumed_log_ratio_sd",
        "pilot_sd_design_multiplier",
        "minimum_runs_per_order_floor",
        "max_order_ratio_fold_difference",
        "mc_search_resamples",
        "mc_search_seed",
        "mc_validation_resamples",
        "mc_validation_seed",
        "analysis_blank_policy",
        "minimum_order_balance_ratio",
        "max_temperature_span_c",
        "max_relative_humidity_span_pct",
        "analysis_bootstrap_resamples",
        "analysis_bootstrap_seed",
    }
    if set(planning_inputs) != expected_planning_input_keys:
        raise ValueError(
            f"planning_inputs fields do not match schema version {SCHEMA_VERSION}"
        )

    expected_protocol_keys = {
        "protocol_id",
        "example_only",
        "execution_eligible",
        "execution_eligibility_rule",
        "lock_eligibility_meaning",
        "prospective_only",
        "hardware_performance_validated",
        "power_basis",
        "actual_bootstrap_gate_validated",
        "current_analyzer_gate_compatible",
        "independent_validation_power_requirement_met",
        "lock_eligible",
        "experimental_scope",
    }
    if set(protocol) != expected_protocol_keys:
        raise ValueError(
            f"protocol fields do not match schema version {SCHEMA_VERSION}"
        )

    expected_fingerprint_keys = {
        "algorithm",
        "canonicalization",
        "canonical_sha256",
        "proves",
        "does_not_prove",
    }
    if set(fingerprint) != expected_fingerprint_keys:
        raise ValueError(
            "protocol_fingerprint fields do not match schema version "
            f"{SCHEMA_VERSION}"
        )
    if fingerprint.get("algorithm") != FINGERPRINT_ALGORITHM:
        raise ValueError("unsupported fingerprint algorithm")
    if fingerprint.get("canonicalization") != FINGERPRINT_CANONICALIZATION:
        raise ValueError("unsupported fingerprint canonicalization")
    if fingerprint.get("proves") != "content_identity_only":
        raise ValueError("fingerprint must be limited to content identity")
    required_limitations = [
        "authorship_or_identity",
        "creation_time_or_pre_registration_chronology",
        "protocol_execution",
        "hardware_performance",
    ]
    if fingerprint.get("does_not_prove") != required_limitations:
        raise ValueError("fingerprint does_not_prove limitations are incomplete")

    stored_sha256 = fingerprint.get("canonical_sha256")
    if (
        not isinstance(stored_sha256, str)
        or len(stored_sha256) != 64
        or any(character not in "0123456789abcdef" for character in stored_sha256)
    ):
        raise ValueError("invalid canonical_sha256")
    calculated_sha256 = canonical_protocol_sha256(document)
    if not hmac.compare_digest(stored_sha256, calculated_sha256):
        raise ValueError("locked protocol fingerprint mismatch")

    protocol_id = _nonempty_text(
        "protocol.protocol_id",
        protocol.get("protocol_id"),
    )
    example_only = _strict_boolean(
        "protocol.example_only", protocol.get("example_only")
    )
    execution_eligible = _strict_boolean(
        "protocol.execution_eligible", protocol.get("execution_eligible")
    )
    lock_eligible = _strict_boolean(
        "protocol.lock_eligible", protocol.get("lock_eligible")
    )
    if protocol.get("execution_eligibility_rule") != (
        "lock_eligible_and_not_example_only"
    ):
        raise ValueError("unsupported execution eligibility rule")
    if protocol.get("lock_eligibility_meaning") != (
        "deterministic_verifier_compatible_not_execution_authorization"
    ):
        raise ValueError("unsupported lock eligibility meaning")
    if execution_eligible != (lock_eligible and not example_only):
        raise ValueError("protocol execution eligibility is internally inconsistent")
    reproduced = plan_power(
        protocol_id, example_only=example_only, **planning_inputs
    )
    if not reproduced["protocol"]["lock_eligible"]:
        raise ValueError("protocol is not compatible with the current analyzer gate")
    if _canonical_protocol_bytes(document) != _canonical_protocol_bytes(reproduced):
        raise ValueError(
            "locked protocol payload is not the deterministic result of planning_inputs"
        )
    if fingerprint != reproduced["protocol_fingerprint"]:
        raise ValueError(
            "locked protocol fingerprint metadata differs from deterministic output"
        )

    result = reproduced["power_plan"]["joint_gate_simulation"]["result"]
    target = reproduced["power_plan"]["joint_gate_simulation"][
        "target_joint_power"
    ]
    if result["wilson_95_percent_lower"] < target:
        raise ValueError("recommended run count misses the target Wilson lower bound")
    gate = reproduced["analysis_gate"]
    recommendation = reproduced["power_plan"]["recommended_independent_runs"]
    if (
        gate["minimum_independent_runs"] != recommendation["total"]
        or gate["minimum_runs_per_order"] != recommendation["per_order"]
        or result["total_independent_runs"] != recommendation["total"]
        or result["runs_per_order"] != recommendation["per_order"]
    ):
        raise ValueError("recommended, simulated, and gate run counts disagree")
    return copy.deepcopy(document)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_without_duplicates(path: os.PathLike[str] | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=_reject_duplicate_json_keys)


def load_locked_protocol(path: os.PathLike[str] | str) -> dict[str, Any]:
    """Read and verify a locked protocol JSON document."""

    document = _load_json_without_duplicates(path)
    return verify_locked_protocol(document)


def _paths_refer_to_same_file(first: Path, second: Path) -> bool:
    try:
        if first.resolve(strict=False) == second.resolve(strict=False):
            return True
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except (OSError, RuntimeError):
        # Resolution uncertainty (including a symlink cycle) is conservatively
        # treated as aliasing for a no-overwrite operation.
        return True


def lock_protocol(
    document: dict[str, Any],
    output_path: os.PathLike[str] | str,
    *,
    input_path: Optional[os.PathLike[str] | str] = None,
) -> dict[str, Any]:
    """Verify and atomically create a read-only protocol file without overwrite."""

    verified = verify_locked_protocol(document)
    destination = Path(output_path)
    if input_path is not None and _paths_refer_to_same_file(Path(input_path), destination):
        raise ValueError("input and output must be different files")
    if not destination.parent.is_dir():
        raise ValueError("output parent directory does not exist")
    data = (json.dumps(verified, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    destination_created = False
    completed = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        destination_created = True
        # Remove the writable temporary name before making the destination
        # read-only; this avoids Windows cleanup failures on read-only temps.
        temporary.unlink()
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        completed = True
    finally:
        if destination_created and not completed:
            try:
                os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
                destination.unlink()
            except OSError:
                pass
        try:
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        except FileNotFoundError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return verified


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser(
        "plan",
        help="plan from a JSON configuration",
        description=(
            "Plan a protocol that binds the 10-field experimental scope, uses "
            "10000..1000000 search/validation MC and analysis-bootstrap resamples, "
            "and requires the resulting total/per-order run counts exactly (no "
            "unplanned continuation)."
        ),
    )
    plan_parser.add_argument(
        "config_json", help="strict JSON planning configuration (duplicate keys fail)"
    )
    verify_parser = subparsers.add_parser(
        "verify", help="read-only deterministic verification of a locked protocol"
    )
    verify_parser.add_argument("locked_json")
    lock_parser = subparsers.add_parser("lock", help="verify and immutably-ish lock a plan")
    lock_parser.add_argument("input_json")
    lock_parser.add_argument("--output", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            document = plan_from_config(
                _load_json_without_duplicates(args.config_json)
            )
            print(json.dumps(document, indent=2, sort_keys=True, allow_nan=False))
            return 0
        if args.command == "verify":
            verified = load_locked_protocol(args.locked_json)
            simulation = verified["power_plan"]["joint_gate_simulation"]
            result = simulation["result"]
            recommendation = verified["power_plan"][
                "recommended_independent_runs"
            ]
            receipt = {
                "verified": True,
                "protocol_id": verified["protocol"]["protocol_id"],
                "example_only": verified["protocol"]["example_only"],
                "execution_eligible": verified["protocol"][
                    "execution_eligible"
                ],
                "recommended_total_independent_runs": recommendation["total"],
                "recommended_runs_per_order": recommendation["per_order"],
                "target_joint_power": simulation["target_joint_power"],
                "estimated_joint_surrogate_power": result[
                    "estimated_joint_power"
                ],
                "wilson_95_percent_lower": result["wilson_95_percent_lower"],
                "canonical_sha256": verified["protocol_fingerprint"][
                    "canonical_sha256"
                ],
                "power_basis": "surrogate_power_only",
                "actual_bootstrap_gate_validated": False,
                "hardware_performance_validated": False,
                "chronology_proven": False,
            }
            print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
            return 0
        input_path = Path(args.input_json)
        output_path = Path(args.output)
        document = _load_json_without_duplicates(input_path)
        verified = lock_protocol(document, output_path, input_path=input_path)
        receipt = {
            "locked": True,
            "output": str(output_path),
            "protocol_id": verified["protocol"]["protocol_id"],
            "example_only": verified["protocol"]["example_only"],
            "execution_eligible": verified["protocol"]["execution_eligible"],
            "canonical_sha256": verified["protocol_fingerprint"]["canonical_sha256"],
            "content_identity_only": True,
            "power_basis": "surrogate_power_only",
            "actual_bootstrap_gate_validated": False,
            "hardware_performance_validated": False,
            "chronology_proven": False,
        }
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {"error": {"type": type(error).__name__, "message": str(error)}},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
