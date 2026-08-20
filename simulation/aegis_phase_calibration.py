"""Reference implementation for Aegis time-of-flight phase calibration.

The module intentionally covers only the deterministic host-side calculation:

* build a planar emitter array in SI units (metres),
* estimate sound speed from distance/time-of-flight measurements,
* calculate the relative delay for every emitter, and
* convert each delay to a wrapped sinusoidal drive phase.

It does not model acoustic pressure, transducer response, multipath,
temperature gradients, sensor/driver latency, or FPGA/actuator I/O.  A fast
result from :func:`benchmark_256_channel_phase_update` therefore demonstrates
calculation latency on the machine that ran it, not physical focusing accuracy
or end-to-end control-loop latency.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import platform
import statistics
import sys
import time
from typing import Callable, Iterable, Mapping, Sequence


TAU = 2.0 * math.pi
UNIVERSAL_GAS_CONSTANT_J_MOL_K = 8.31446261815324
DEFAULT_TEMPERATURE_K = 293.15


@dataclass(frozen=True)
class GasProperties:
    """Ideal-gas properties used only to generate deterministic examples."""

    heat_capacity_ratio: float
    molar_mass_kg_mol: float


GAS_PROPERTIES: Mapping[str, GasProperties] = {
    "air": GasProperties(heat_capacity_ratio=1.4000, molar_mass_kg_mol=0.02896546),
    "n2": GasProperties(heat_capacity_ratio=1.4000, molar_mass_kg_mol=0.02801340),
    "he": GasProperties(heat_capacity_ratio=5.0 / 3.0, molar_mass_kg_mol=0.004002602),
}


Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class ToFCalibration:
    """Result of fitting ``time = offset + distance / sound_speed``."""

    sound_speed_m_s: float
    time_offset_s: float
    rms_residual_s: float
    sample_count: int
    fit_time_offset: bool


@dataclass(frozen=True)
class FocusSolution:
    """Per-channel geometric focusing commands, all expressed in SI units.

    ``phase_rad`` assumes a channel drive of ``cos(2*pi*f*t + phase_rad)``.
    A nearer emitter receives a positive start delay so all direct-path signals
    arrive at the target at the same reference time.  Its equivalent phase is
    therefore ``wrap(-2*pi*f*delay)``.
    """

    coordinates_m: tuple[Point3, ...]
    target_m: Point3
    sound_speed_m_s: float
    frequency_hz: float
    distance_m: tuple[float, ...]
    propagation_time_s: tuple[float, ...]
    delay_s: tuple[float, ...]
    phase_rad: tuple[float, ...]
    reference_arrival_time_s: float

    @property
    def channel_count(self) -> int:
        return len(self.coordinates_m)


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


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _point3(name: str, value: Sequence[float]) -> Point3:
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


def _positive_series(name: str, values: Iterable[float]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a numeric iterable")
    try:
        result = tuple(_positive_float(f"{name}[{index}]", value)
                       for index, value in enumerate(values))
    except TypeError as exc:
        if str(exc).startswith(name):
            raise
        raise TypeError(f"{name} must be a numeric iterable") from exc
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def planar_array_coordinates(
    rows: int,
    columns: int,
    pitch_x_m: float,
    pitch_y_m: float | None = None,
    origin_m: Sequence[float] = (0.0, 0.0, 0.0),
) -> tuple[Point3, ...]:
    """Return row-major coordinates for a centred rectangular planar array.

    Args:
        rows: Positive number of rows along the y axis.
        columns: Positive number of columns along the x axis.
        pitch_x_m: Centre-to-centre column spacing in metres.
        pitch_y_m: Row spacing in metres; defaults to ``pitch_x_m``.
        origin_m: Array centre ``(x, y, z)`` in metres.
    """

    rows = _positive_int("rows", rows)
    columns = _positive_int("columns", columns)
    pitch_x_m = _positive_float("pitch_x_m", pitch_x_m)
    pitch_y_m = pitch_x_m if pitch_y_m is None else _positive_float(
        "pitch_y_m", pitch_y_m
    )
    origin_x, origin_y, origin_z = _point3("origin_m", origin_m)

    x_midpoint = (columns - 1) / 2.0
    y_midpoint = (rows - 1) / 2.0
    return tuple(
        (
            origin_x + (column - x_midpoint) * pitch_x_m,
            origin_y + (row - y_midpoint) * pitch_y_m,
            origin_z,
        )
        for row in range(rows)
        for column in range(columns)
    )


def ideal_gas_sound_speed(
    gas: str,
    temperature_k: float = DEFAULT_TEMPERATURE_K,
) -> float:
    """Return ``sqrt(gamma*R*T/M)`` for an example gas.

    This ideal-gas value is a reproducible example input, not a substitute for
    an in-situ ToF measurement.  Humidity, composition, and temperature fields
    can make the actual path-averaged speed differ.
    """

    if not isinstance(gas, str):
        raise TypeError("gas must be a string")
    gas_key = gas.strip().lower()
    if gas_key not in GAS_PROPERTIES:
        supported = ", ".join(sorted(GAS_PROPERTIES))
        raise ValueError(f"unsupported gas {gas!r}; expected one of: {supported}")
    temperature_k = _positive_float("temperature_k", temperature_k)
    properties = GAS_PROPERTIES[gas_key]
    return math.sqrt(
        properties.heat_capacity_ratio
        * UNIVERSAL_GAS_CONSTANT_J_MOL_K
        * temperature_k
        / properties.molar_mass_kg_mol
    )


def estimate_sound_speed_from_tof(
    distances_m: Iterable[float],
    times_s: Iterable[float],
    *,
    fit_time_offset: bool = True,
) -> ToFCalibration:
    """Estimate sound speed by least-squares regression of ToF against distance.

    With ``fit_time_offset=True`` (the default), at least two distinct path
    lengths are required and the model fits a shared electronics/trigger offset:
    ``time_s = time_offset_s + distance_m / sound_speed_m_s``.  When false, the
    fit is constrained through the origin.
    """

    if not isinstance(fit_time_offset, bool):
        raise TypeError("fit_time_offset must be a bool")
    distances = _positive_series("distances_m", distances_m)
    times = _positive_series("times_s", times_s)
    if len(distances) != len(times):
        raise ValueError("distances_m and times_s must have the same length")

    sample_count = len(distances)
    if fit_time_offset:
        if sample_count < 2:
            raise ValueError("at least two ToF samples are required to fit an offset")
        mean_distance = statistics.fmean(distances)
        mean_time = statistics.fmean(times)
        denominator = sum((distance - mean_distance) ** 2 for distance in distances)
        if denominator == 0.0:
            raise ValueError("distances_m must contain at least two distinct values")
        slope_s_m = sum(
            (distance - mean_distance) * (tof - mean_time)
            for distance, tof in zip(distances, times)
        ) / denominator
        time_offset_s = mean_time - slope_s_m * mean_distance
    else:
        denominator = sum(distance * distance for distance in distances)
        slope_s_m = sum(
            distance * tof for distance, tof in zip(distances, times)
        ) / denominator
        time_offset_s = 0.0

    if not math.isfinite(slope_s_m) or slope_s_m <= 0.0:
        raise ValueError("ToF data must produce a positive finite distance/time slope")

    sound_speed_m_s = 1.0 / slope_s_m
    residuals = tuple(
        tof - (time_offset_s + slope_s_m * distance)
        for distance, tof in zip(distances, times)
    )
    rms_residual_s = math.sqrt(statistics.fmean(value * value for value in residuals))
    return ToFCalibration(
        sound_speed_m_s=sound_speed_m_s,
        time_offset_s=time_offset_s,
        rms_residual_s=rms_residual_s,
        sample_count=sample_count,
        fit_time_offset=fit_time_offset,
    )


def wrap_phase_rad(phase_rad: float) -> float:
    """Wrap a finite phase angle to the half-open interval ``[0, 2*pi)``."""

    phase_rad = _finite_float("phase_rad", phase_rad)
    wrapped = phase_rad % TAU
    return 0.0 if wrapped == 0.0 else wrapped


def calculate_focus_solution(
    coordinates_m: Iterable[Sequence[float]],
    target_m: Sequence[float],
    sound_speed_m_s: float,
    frequency_hz: float,
) -> FocusSolution:
    """Calculate direct-path relative delay and wrapped phase for every channel."""

    if isinstance(coordinates_m, (str, bytes)):
        raise TypeError("coordinates_m must be an iterable of three-dimensional points")
    try:
        coordinates = tuple(
            _point3(f"coordinates_m[{index}]", point)
            for index, point in enumerate(coordinates_m)
        )
    except TypeError as exc:
        if str(exc).startswith("coordinates_m["):
            raise
        raise TypeError(
            "coordinates_m must be an iterable of three-dimensional points"
        ) from exc
    if not coordinates:
        raise ValueError("coordinates_m must contain at least one channel")

    target = _point3("target_m", target_m)
    sound_speed_m_s = _positive_float("sound_speed_m_s", sound_speed_m_s)
    frequency_hz = _positive_float("frequency_hz", frequency_hz)

    target_x, target_y, target_z = target
    distances = tuple(
        math.sqrt(
            (target_x - emitter_x) ** 2
            + (target_y - emitter_y) ** 2
            + (target_z - emitter_z) ** 2
        )
        for emitter_x, emitter_y, emitter_z in coordinates
    )
    if any(distance == 0.0 for distance in distances):
        raise ValueError("target_m must not coincide with an emitter coordinate")

    propagation_times = tuple(distance / sound_speed_m_s for distance in distances)
    reference_arrival_time_s = max(propagation_times)
    delays = tuple(reference_arrival_time_s - tof for tof in propagation_times)
    phases = tuple(wrap_phase_rad(-TAU * frequency_hz * delay) for delay in delays)

    return FocusSolution(
        coordinates_m=coordinates,
        target_m=target,
        sound_speed_m_s=sound_speed_m_s,
        frequency_hz=frequency_hz,
        distance_m=distances,
        propagation_time_s=propagation_times,
        delay_s=delays,
        phase_rad=phases,
        reference_arrival_time_s=reference_arrival_time_s,
    )


def _maximum_arrival_phase_error_rad(solution: FocusSolution) -> float:
    omega = TAU * solution.frequency_hz
    arrival_phases = tuple(
        wrap_phase_rad(phase - omega * propagation_time)
        for phase, propagation_time in zip(
            solution.phase_rad, solution.propagation_time_s
        )
    )
    reference = arrival_phases[0]
    return max(
        abs(math.atan2(math.sin(value - reference), math.cos(value - reference)))
        for value in arrival_phases
    )


def run_gas_examples(
    temperature_k: float = DEFAULT_TEMPERATURE_K,
) -> dict[str, object]:
    """Run deterministic synthetic ToF examples for air, N2, and helium."""

    temperature_k = _positive_float("temperature_k", temperature_k)
    rows = columns = 16
    pitch_m = 0.004
    frequency_hz = 40_000.0
    target_m = (0.010, -0.005, 0.120)
    calibration_distances_m = (0.050, 0.100, 0.150, 0.200)
    synthetic_time_offset_s = 18.0e-6
    coordinates = planar_array_coordinates(rows, columns, pitch_m)

    examples: list[dict[str, object]] = []
    for gas in ("air", "n2", "he"):
        reference_speed_m_s = ideal_gas_sound_speed(gas, temperature_k)
        synthetic_times_s = tuple(
            synthetic_time_offset_s + distance / reference_speed_m_s
            for distance in calibration_distances_m
        )
        calibration = estimate_sound_speed_from_tof(
            calibration_distances_m,
            synthetic_times_s,
        )
        solution = calculate_focus_solution(
            coordinates,
            target_m,
            calibration.sound_speed_m_s,
            frequency_hz,
        )
        examples.append(
            {
                "gas": gas,
                "ideal_reference_speed_m_s": reference_speed_m_s,
                "tof_estimated_speed_m_s": calibration.sound_speed_m_s,
                "speed_error_m_s": calibration.sound_speed_m_s
                - reference_speed_m_s,
                "fitted_time_offset_s": calibration.time_offset_s,
                "tof_rms_residual_s": calibration.rms_residual_s,
                "max_relative_delay_s": max(solution.delay_s),
                "max_arrival_phase_error_rad": _maximum_arrival_phase_error_rad(
                    solution
                ),
            }
        )

    return {
        "example_kind": "synthetic ideal-gas ToF; not measured data",
        "temperature_k": temperature_k,
        "array": {
            "rows": rows,
            "columns": columns,
            "channels": len(coordinates),
            "pitch_x_m": pitch_m,
            "pitch_y_m": pitch_m,
        },
        "frequency_hz": frequency_hz,
        "target_m": target_m,
        "calibration_distances_m": calibration_distances_m,
        "synthetic_time_offset_s": synthetic_time_offset_s,
        "examples": examples,
        "physical_accuracy_validated": False,
        "physical_accuracy_note": (
            "The examples validate equations and units against exact synthetic ToF "
            "inputs. Chamber measurements are required to validate physical accuracy."
        ),
    }


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
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


def benchmark_256_channel_phase_update(
    iterations: int = 1_000,
    warmup_iterations: int = 25,
    *,
    budget_ms: float = 100.0,
    gas: str = "air",
    temperature_k: float = DEFAULT_TEMPERATURE_K,
    _timer_ns: Callable[[], int] = time.perf_counter_ns,
) -> dict[str, object]:
    """Measure repeated 256-channel host-side calibration calculations.

    Each timed iteration fits sound speed from four synthetic ToF samples and
    recalculates all 256 geometric delays and phases.  Coordinates and example
    inputs are allocated before timing.  The budget verdict uses p95 latency.

    ``_timer_ns`` exists for deterministic tests; production callers should use
    the default monotonic high-resolution clock.
    """

    iterations = _positive_int("iterations", iterations)
    warmup_iterations = _nonnegative_int("warmup_iterations", warmup_iterations)
    budget_ms = _positive_float("budget_ms", budget_ms)
    temperature_k = _positive_float("temperature_k", temperature_k)
    if not callable(_timer_ns):
        raise TypeError("_timer_ns must be callable")

    coordinates = planar_array_coordinates(16, 16, 0.004)
    target_m = (0.010, -0.005, 0.120)
    frequency_hz = 40_000.0
    reference_speed_m_s = ideal_gas_sound_speed(gas, temperature_k)
    distances_m = (0.050, 0.100, 0.150, 0.200)
    time_offset_s = 18.0e-6
    times_s = tuple(time_offset_s + distance / reference_speed_m_s
                    for distance in distances_m)

    def update_once() -> FocusSolution:
        calibration = estimate_sound_speed_from_tof(distances_m, times_s)
        return calculate_focus_solution(
            coordinates,
            target_m,
            calibration.sound_speed_m_s,
            frequency_hz,
        )

    checksum = 0.0
    for _ in range(warmup_iterations):
        solution = update_once()
        checksum += solution.phase_rad[0]

    elapsed_ms: list[float] = []
    for _ in range(iterations):
        started_ns = _timer_ns()
        solution = update_once()
        finished_ns = _timer_ns()
        if finished_ns < started_ns:
            raise RuntimeError("timer moved backwards")
        elapsed_ms.append((finished_ns - started_ns) / 1_000_000.0)
        checksum += solution.phase_rad[0]

    p95_ms = _percentile(elapsed_ms, 0.95)
    p99_ms = _percentile(elapsed_ms, 0.99)
    maximum_ms = max(elapsed_ms)
    return {
        "channels": len(coordinates),
        "iterations": iterations,
        "warmup_iterations": warmup_iterations,
        "gas": gas.strip().lower(),
        "temperature_k": temperature_k,
        "frequency_hz": frequency_hz,
        "timing": {
            "minimum_ms": min(elapsed_ms),
            "median_ms": statistics.median(elapsed_ms),
            "mean_ms": statistics.fmean(elapsed_ms),
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "maximum_ms": maximum_ms,
        },
        "budget_ms": budget_ms,
        "budget_metric": "p95_ms",
        "within_budget": p95_ms <= budget_ms,
        "all_samples_within_budget": maximum_ms <= budget_ms,
        "timer": "time.perf_counter_ns",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "checksum": checksum,
        "benchmark_scope": (
            "Host CPU only: four-point synthetic ToF fit plus direct-path "
            "distance, relative-delay, and wrapped-phase calculation for 256 channels."
        ),
        "excluded_from_benchmark": [
            "sensor acquisition and timestamp accuracy",
            "transport and driver latency",
            "FPGA/DAC update latency",
            "transducer settling and acoustic propagation",
            "multipath and environmental estimation",
        ],
        "physical_accuracy_validated": False,
    }


def _json_print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def _print_examples(result: Mapping[str, object]) -> None:
    print("Aegis phase-calibration synthetic examples")
    print(f"Array: {result['array']}")
    print(f"Frequency: {result['frequency_hz']:.0f} Hz")
    for example in result["examples"]:
        print(
            f"{example['gas']:>3}: reference={example['ideal_reference_speed_m_s']:.3f} "
            f"m/s, ToF estimate={example['tof_estimated_speed_m_s']:.3f} m/s, "
            f"max delay={example['max_relative_delay_s'] * 1e6:.3f} us"
        )
    print("Physical accuracy: NOT VALIDATED (synthetic inputs only).")


def _print_benchmark(result: Mapping[str, object]) -> None:
    timing = result["timing"]
    print("Aegis 256-channel phase-calculation benchmark")
    print(
        f"iterations={result['iterations']}, median={timing['median_ms']:.6f} ms, "
        f"p95={timing['p95_ms']:.6f} ms, p99={timing['p99_ms']:.6f} ms, "
        f"max={timing['maximum_ms']:.6f} ms"
    )
    print(
        f"p95 budget <= {result['budget_ms']:.3f} ms: "
        f"{'PASS' if result['within_budget'] else 'FAIL'}"
    )
    print(f"Scope: {result['benchmark_scope']}")
    print("Physical accuracy: NOT VALIDATED by this timing benchmark.")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aegis SI-unit ToF and phase-calibration reference implementation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    examples_parser = subparsers.add_parser(
        "examples", help="run deterministic air/N2/He synthetic examples"
    )
    examples_parser.add_argument(
        "--temperature-k", type=float, default=DEFAULT_TEMPERATURE_K
    )
    examples_parser.add_argument("--json", action="store_true", dest="as_json")

    benchmark_parser = subparsers.add_parser(
        "benchmark", help="benchmark a repeated 256-channel host calculation"
    )
    benchmark_parser.add_argument("--iterations", type=int, default=1_000)
    benchmark_parser.add_argument("--warmup-iterations", type=int, default=25)
    benchmark_parser.add_argument("--budget-ms", type=float, default=100.0)
    benchmark_parser.add_argument("--gas", choices=sorted(GAS_PROPERTIES), default="air")
    benchmark_parser.add_argument(
        "--temperature-k", type=float, default=DEFAULT_TEMPERATURE_K
    )
    benchmark_parser.add_argument("--json", action="store_true", dest="as_json")
    benchmark_parser.add_argument(
        "--fail-on-budget",
        action="store_true",
        help="return exit status 2 if p95 exceeds --budget-ms",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.command == "examples":
        result = run_gas_examples(args.temperature_k)
        _json_print(result) if args.as_json else _print_examples(result)
        return 0

    result = benchmark_256_channel_phase_update(
        iterations=args.iterations,
        warmup_iterations=args.warmup_iterations,
        budget_ms=args.budget_ms,
        gas=args.gas,
        temperature_k=args.temperature_k,
    )
    _json_print(result) if args.as_json else _print_benchmark(result)
    if args.fail_on_budget and not result["within_budget"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
