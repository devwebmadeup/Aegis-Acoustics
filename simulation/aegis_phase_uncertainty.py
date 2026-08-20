"""Monte Carlo sensitivity analysis for Aegis ToF phase calibration.

This module adds independent, zero-mean Gaussian noise to the timestamp and
reference-distance inputs of a synthetic multi-point time-of-flight (ToF)
calibration.  It then reports the resulting sound-speed estimation error and
the relative arrival-phase error of a 16 x 16 (256-channel) planar array.

All public calculation inputs use SI units.  The simulation is deterministic
for a given integer seed, but it is not a hardware validation.  In particular,
one fitted sound speed is only a path-averaged scalar: it cannot represent
spatial temperature/composition gradients, turbulence, multipath, dispersion,
or different propagation conditions from each emitter to the focus.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import random
import statistics
import sys
from typing import Iterable, Mapping, Sequence

try:
    # Package import used by ``python -m`` and the unit tests.
    from simulation import aegis_phase_calibration as calibration
except ModuleNotFoundError:  # pragma: no cover - exercised by direct CLI use.
    # Direct execution puts ``simulation/`` rather than the repository root on
    # sys.path, so the sibling module is imported without its package prefix.
    import aegis_phase_calibration as calibration


DEFAULT_SEED = 20260820
DEFAULT_TRIALS = 2_000
DEFAULT_TRUE_SOUND_SPEED_M_S = 343.25
DEFAULT_TIME_OFFSET_S = 18.0e-6
DEFAULT_TIMESTAMP_NOISE_STD_S = 100.0e-9
DEFAULT_DISTANCE_NOISE_STD_M = 50.0e-6
DEFAULT_FREQUENCY_HZ = 40_000.0
DEFAULT_PHASE_ERROR_BUDGET_RAD = math.radians(1.0)
DEFAULT_CALIBRATION_DISTANCES_M = (0.050, 0.100, 0.150, 0.200)
DEFAULT_TARGET_M = (0.010, -0.005, 0.120)
ARRAY_ROWS = 16
ARRAY_COLUMNS = 16
ARRAY_PITCH_M = 0.004
TAU = 2.0 * math.pi


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if result <= 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _nonnegative_float(name: str, value: object) -> float:
    result = _finite_float(name, value)
    if result < 0.0:
        raise ValueError(f"{name} must not be negative")
    return result


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _positive_series(name: str, values: Iterable[float]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a numeric iterable")
    try:
        result = tuple(
            _positive_float(f"{name}[{index}]", value)
            for index, value in enumerate(values)
        )
    except TypeError as exc:
        if str(exc).startswith(name):
            raise
        raise TypeError(f"{name} must be a numeric iterable") from exc
    if len(result) < 2:
        raise ValueError(f"{name} must contain at least two values")
    if len(set(result)) < 2:
        raise ValueError(f"{name} must contain at least two distinct values")
    return result


def _point3(name: str, value: Sequence[float]) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a three-element numeric sequence")
    try:
        items = tuple(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be a three-element numeric sequence") from exc
    if len(items) != 3:
        raise ValueError(f"{name} must contain exactly three values")
    return (
        _finite_float(f"{name}[0]", items[0]),
        _finite_float(f"{name}[1]", items[1]),
        _finite_float(f"{name}[2]", items[2]),
    )


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Return a linearly interpolated percentile for a non-empty sequence."""

    if not values:
        raise ValueError("values must not be empty")
    fraction = _finite_float("fraction", fraction)
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _absolute_summary(values: Sequence[float]) -> dict[str, float]:
    """Summarise non-negative SI-valued observations."""

    if not values:
        raise ValueError("values must not be empty")
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "maximum": max(values),
        "mean": statistics.fmean(values),
    }


def _signed_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        raise ValueError("values must not be empty")
    return {
        "minimum": min(values),
        "p50": _percentile(values, 0.50),
        "maximum": max(values),
        "mean": statistics.fmean(values),
        "population_std": statistics.pstdev(values),
    }


def _circular_abs_difference_rad(first: float, second: float) -> float:
    difference = first - second
    return abs(math.atan2(math.sin(difference), math.cos(difference)))


def _relative_arrival_phase_errors_rad(
    estimated_phase_rad: Sequence[float],
    true_propagation_time_s: Sequence[float],
    frequency_hz: float,
) -> tuple[float, ...]:
    """Return per-channel phase mismatch relative to channel zero.

    The shared absolute phase is irrelevant to focusing, so the first channel
    is the reference.  Its error is exactly zero.  Propagation uses the true
    synthetic sound speed, while drive phases use the noisy ToF estimate.
    """

    if len(estimated_phase_rad) != len(true_propagation_time_s):
        raise ValueError("phase and propagation-time sequences must have equal length")
    if not estimated_phase_rad:
        raise ValueError("phase sequences must not be empty")
    omega = TAU * frequency_hz
    arrival_phase_rad = tuple(
        phase_rad - omega * propagation_time_s
        for phase_rad, propagation_time_s in zip(
            estimated_phase_rad, true_propagation_time_s
        )
    )
    reference = arrival_phase_rad[0]
    return tuple(
        _circular_abs_difference_rad(value, reference)
        for value in arrival_phase_rad
    )


def run_phase_uncertainty_monte_carlo(
    *,
    trials: int = DEFAULT_TRIALS,
    seed: int = DEFAULT_SEED,
    timestamp_noise_std_s: float = DEFAULT_TIMESTAMP_NOISE_STD_S,
    distance_noise_std_m: float = DEFAULT_DISTANCE_NOISE_STD_M,
    true_sound_speed_m_s: float = DEFAULT_TRUE_SOUND_SPEED_M_S,
    time_offset_s: float = DEFAULT_TIME_OFFSET_S,
    calibration_distances_m: Iterable[float] = DEFAULT_CALIBRATION_DISTANCES_M,
    frequency_hz: float = DEFAULT_FREQUENCY_HZ,
    phase_error_budget_rad: float = DEFAULT_PHASE_ERROR_BUDGET_RAD,
    target_m: Sequence[float] = DEFAULT_TARGET_M,
) -> dict[str, object]:
    """Evaluate noisy multi-point ToF calibration and 256-channel phase error.

    ``timestamp_noise_std_s`` and ``distance_noise_std_m`` are independent
    Gaussian one-sigma values applied separately to every calibration point in
    every trial.  The acceptance metric is the p95 across trials of each
    trial's worst absolute relative arrival-phase error over all 256 channels.

    A Gaussian has unbounded support.  A trial that produces a non-positive
    measured distance/time or non-physical regression slope is retained as an
    invalid trial instead of being silently resampled.  Any invalid trial makes
    the acceptance verdict fail.
    """

    trials = _positive_int("trials", trials)
    seed = _integer("seed", seed)
    timestamp_noise_std_s = _nonnegative_float(
        "timestamp_noise_std_s", timestamp_noise_std_s
    )
    distance_noise_std_m = _nonnegative_float(
        "distance_noise_std_m", distance_noise_std_m
    )
    true_sound_speed_m_s = _positive_float(
        "true_sound_speed_m_s", true_sound_speed_m_s
    )
    time_offset_s = _nonnegative_float("time_offset_s", time_offset_s)
    frequency_hz = _positive_float("frequency_hz", frequency_hz)
    phase_error_budget_rad = _positive_float(
        "phase_error_budget_rad", phase_error_budget_rad
    )
    distances_m = _positive_series(
        "calibration_distances_m", calibration_distances_m
    )
    target = _point3("target_m", target_m)

    coordinates = calibration.planar_array_coordinates(
        ARRAY_ROWS, ARRAY_COLUMNS, ARRAY_PITCH_M
    )
    true_solution = calibration.calculate_focus_solution(
        coordinates,
        target,
        true_sound_speed_m_s,
        frequency_hz,
    )
    if true_solution.channel_count != 256:  # Defensive invariant for reports.
        raise RuntimeError("uncertainty model requires exactly 256 channels")

    rng = random.Random(seed)
    signed_speed_errors_m_s: list[float] = []
    absolute_speed_errors_m_s: list[float] = []
    absolute_speed_errors_fraction: list[float] = []
    trial_max_phase_errors_rad: list[float] = []
    all_channel_phase_errors_rad: list[float] = []
    invalid_reasons: Counter[str] = Counter()

    exact_times_s = tuple(
        time_offset_s + distance_m / true_sound_speed_m_s
        for distance_m in distances_m
    )

    for _ in range(trials):
        measured_distances_m = tuple(
            distance_m + rng.gauss(0.0, distance_noise_std_m)
            for distance_m in distances_m
        )
        measured_times_s = tuple(
            tof_s + rng.gauss(0.0, timestamp_noise_std_s)
            for tof_s in exact_times_s
        )

        if any(value <= 0.0 for value in measured_distances_m):
            invalid_reasons["nonpositive_measured_distance"] += 1
            continue
        if any(value <= 0.0 for value in measured_times_s):
            invalid_reasons["nonpositive_measured_time"] += 1
            continue

        try:
            fitted = calibration.estimate_sound_speed_from_tof(
                measured_distances_m,
                measured_times_s,
                fit_time_offset=True,
            )
        except ValueError:
            invalid_reasons["nonphysical_tof_regression"] += 1
            continue

        estimated_solution = calibration.calculate_focus_solution(
            coordinates,
            target,
            fitted.sound_speed_m_s,
            frequency_hz,
        )
        phase_errors_rad = _relative_arrival_phase_errors_rad(
            estimated_solution.phase_rad,
            true_solution.propagation_time_s,
            frequency_hz,
        )

        signed_speed_error_m_s = (
            fitted.sound_speed_m_s - true_sound_speed_m_s
        )
        absolute_speed_error_m_s = abs(signed_speed_error_m_s)
        signed_speed_errors_m_s.append(signed_speed_error_m_s)
        absolute_speed_errors_m_s.append(absolute_speed_error_m_s)
        absolute_speed_errors_fraction.append(
            absolute_speed_error_m_s / true_sound_speed_m_s
        )
        trial_max_phase_errors_rad.append(max(phase_errors_rad))
        all_channel_phase_errors_rad.extend(phase_errors_rad)

    valid_trials = len(signed_speed_errors_m_s)
    invalid_trials = trials - valid_trials
    if valid_trials == 0:
        raise RuntimeError(
            "all Monte Carlo trials were non-physical; reduce the input noise"
        )

    trial_max_summary = _absolute_summary(trial_max_phase_errors_rad)
    observed_rad = trial_max_summary["p95"]
    within_phase_budget = observed_rad <= phase_error_budget_rad
    accepted = invalid_trials == 0 and within_phase_budget
    maximum_tick_for_full_phase_budget_s = (
        phase_error_budget_rad / (TAU * frequency_hz)
    )

    return {
        "analysis_kind": (
            "seeded synthetic multi-point ToF Monte Carlo sensitivity analysis"
        ),
        "units": {
            "distance": "m",
            "time": "s",
            "sound_speed": "m/s",
            "phase": "rad",
            "frequency": "Hz",
        },
        "configuration": {
            "trials": trials,
            "seed": seed,
            "true_sound_speed_m_s": true_sound_speed_m_s,
            "time_offset_s": time_offset_s,
            "timestamp_noise_std_s": timestamp_noise_std_s,
            "distance_noise_std_m": distance_noise_std_m,
            "calibration_distances_m": distances_m,
            "frequency_hz": frequency_hz,
            "target_m": target,
            "array": {
                "rows": ARRAY_ROWS,
                "columns": ARRAY_COLUMNS,
                "channels": true_solution.channel_count,
                "pitch_m": ARRAY_PITCH_M,
            },
        },
        "trial_accounting": {
            "requested": trials,
            "valid": valid_trials,
            "invalid": invalid_trials,
            "invalid_fraction": invalid_trials / trials,
            "invalid_reasons": dict(sorted(invalid_reasons.items())),
        },
        "sound_speed_error": {
            "signed_m_s": _signed_summary(signed_speed_errors_m_s),
            "absolute_m_s": _absolute_summary(absolute_speed_errors_m_s),
            "absolute_fraction": _absolute_summary(
                absolute_speed_errors_fraction
            ),
        },
        "arrival_phase_error": {
            "definition": (
                "absolute direct-path arrival-phase mismatch relative to channel "
                "zero after applying phases calculated from the fitted sound speed"
            ),
            "trial_max_absolute_rad": trial_max_summary,
            "all_channel_absolute_rad": _absolute_summary(
                all_channel_phase_errors_rad
            ),
            "channel_observations": len(all_channel_phase_errors_rad),
        },
        "acceptance": {
            "metric": "trial_max_absolute_rad.p95",
            "threshold_rad": phase_error_budget_rad,
            "threshold_origin": "user-supplied engineering criterion",
            "observed_rad": observed_rad,
            "no_invalid_trials_required": True,
            "within_phase_budget": within_phase_budget,
            "passed": accepted,
        },
        "phase_quantization_design_bound": {
            "maximum_tick_s_if_full_budget_is_allocated_to_quantization": (
                maximum_tick_for_full_phase_budget_s
            ),
            "derivation": (
                "worst relative error between two independently rounded channel "
                "delays is omega*tick; require omega*tick <= phase budget"
            ),
            "quantization_simulated_in_monte_carlo": False,
            "combination_note": (
                "This is a standalone conservative allocation. It must be reduced "
                "when calibration, clock, driver, and channel errors share the budget."
            ),
        },
        "hardware_accuracy_validated": False,
        "noise_parameters_measured_on_aegis_hardware": False,
        "hardware_accuracy_note": (
            "Hardware accuracy not validated: this result quantifies numerical "
            "sensitivity under synthetic assumptions only."
        ),
        "model_limitations": [
            (
                "A single spatially uniform, nondispersive mean sound speed is "
                "fitted; this is physically inadequate for temperature, humidity, "
                "or composition gradients and unequal emitter-to-focus paths."
            ),
            (
                "Timestamp and reference-distance errors are independent, "
                "zero-mean Gaussian samples; bias, drift, correlation, outliers, "
                "clock quantisation, and calibration-target motion are excluded."
            ),
            (
                "The default noise levels and phase-error budget are engineering "
                "assumptions, not specifications measured on Aegis hardware."
            ),
            (
                "Only direct geometric paths are modelled; multipath, turbulence, "
                "flow/Doppler effects, attenuation, and transducer response are excluded."
            ),
            (
                "Distance noise applies to the ToF calibration baselines only; "
                "array placement, target localisation, and per-channel position "
                "uncertainty are not simulated."
            ),
            (
                "Sensor acquisition, control transport, phase quantisation, driver "
                "latency, channel mismatch, and acoustic settling are excluded from "
                "the Monte Carlo; only a standalone quantisation design bound is reported."
            ),
        ],
    }


def _print_human(result: Mapping[str, object]) -> None:
    configuration = result["configuration"]
    accounting = result["trial_accounting"]
    speed = result["sound_speed_error"]["absolute_m_s"]
    phase = result["arrival_phase_error"]["trial_max_absolute_rad"]
    acceptance = result["acceptance"]
    quantisation = result["phase_quantization_design_bound"]
    print("Aegis phase-calibration uncertainty analysis")
    print(
        f"trials={accounting['requested']}, valid={accounting['valid']}, "
        f"seed={configuration['seed']}, channels={configuration['array']['channels']}"
    )
    print(
        "absolute sound-speed error [m/s]: "
        f"p50={speed['p50']:.6g}, p95={speed['p95']:.6g}, "
        f"p99={speed['p99']:.6g}, max={speed['maximum']:.6g}"
    )
    print(
        "trial maximum arrival-phase error [rad]: "
        f"p50={phase['p50']:.6g}, p95={phase['p95']:.6g}, "
        f"p99={phase['p99']:.6g}, max={phase['maximum']:.6g}"
    )
    print(
        f"acceptance ({acceptance['metric']} <= "
        f"{acceptance['threshold_rad']:.6g} rad): "
        f"{'PASS' if acceptance['passed'] else 'FAIL'}"
    )
    print(
        "standalone maximum delay tick if the full phase budget is allocated "
        f"to quantisation: "
        f"{quantisation['maximum_tick_s_if_full_budget_is_allocated_to_quantization'] * 1e9:.6g} ns"
    )
    print(result["hardware_accuracy_note"])


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seeded SI-unit Monte Carlo sensitivity analysis for synthetic ToF "
            "sound-speed calibration and 256-channel arrival phase"
        )
    )
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--timestamp-noise-std-s",
        type=float,
        default=DEFAULT_TIMESTAMP_NOISE_STD_S,
        help="one-sigma ToF timestamp noise in seconds",
    )
    parser.add_argument(
        "--distance-noise-std-m",
        type=float,
        default=DEFAULT_DISTANCE_NOISE_STD_M,
        help="one-sigma calibration-reference distance noise in metres",
    )
    parser.add_argument(
        "--true-sound-speed-m-s", type=float, default=DEFAULT_TRUE_SOUND_SPEED_M_S
    )
    parser.add_argument("--time-offset-s", type=float, default=DEFAULT_TIME_OFFSET_S)
    parser.add_argument("--frequency-hz", type=float, default=DEFAULT_FREQUENCY_HZ)
    parser.add_argument(
        "--phase-error-budget-rad",
        type=float,
        default=DEFAULT_PHASE_ERROR_BUDGET_RAD,
        help="maximum accepted p95 trial-worst relative arrival phase in radians",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--fail-on-budget",
        action="store_true",
        help="return exit status 2 when the phase-error acceptance test fails",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    try:
        result = run_phase_uncertainty_monte_carlo(
            trials=args.trials,
            seed=args.seed,
            timestamp_noise_std_s=args.timestamp_noise_std_s,
            distance_noise_std_m=args.distance_noise_std_m,
            true_sound_speed_m_s=args.true_sound_speed_m_s,
            time_offset_s=args.time_offset_s,
            frequency_hz=args.frequency_hz,
            phase_error_budget_rad=args.phase_error_budget_rad,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    else:
        _print_human(result)
    if args.fail_on_budget and not result["acceptance"]["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
