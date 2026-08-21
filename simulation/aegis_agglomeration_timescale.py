"""Quantify the concentration-squared (n^2) barrier raised in
docs/HYBRID_AGGLOMERATION_RESEARCH.md for acoustic-agglomeration hybrids.

This module does not model an acoustic field at all.  It computes only the
baseline Brownian (perikinetic) coagulation timescale -- the rate at which
particles of a given size would find each other by diffusion alone, at a
given number concentration.  Any acoustic/electrostatic enhancement reported
in the literature multiplies this baseline; no citable, general-purpose
enhancement-factor formula was found during that research, so none is
asserted here.  The question this module answers is narrower and more
defensible: given the literature's validated concentrations (industrial
exhaust, ~1e6-1e9 particles/cm^3) versus a semiconductor cleanroom's design
concentration (ISO 14644-1, as low as ~10 particles/m^3), how many orders of
magnitude does the coagulation rate differ for the same particle size and the
same kernel?  Because the two-body Brownian kernel K(a) is held fixed between
the two cases, the cleanroom/exhaust timescale ratio reduces exactly to the
inverse concentration ratio -- a result that does not depend on how precisely
K itself is modeled.

Kernel: Smoluchowski/Fuchs Brownian coagulation kernel with Cunningham slip
correction (continuum form), as given in standard aerosol-physics references
(e.g. Seinfeld & Pandis, "Atmospheric Chemistry and Physics", ch. 13;
Friedlander, "Smoke, Dust, and Haze"):

    D(a)    = kB*T*Cc(a) / (6*pi*eta*a)
    Cc(a)   = 1 + Kn*(1.257 + 0.4*exp(-1.1/Kn)),  Kn = lambda_air / a
    K(a,b)  = 4*pi*(a+b)*(D(a)+D(b))

For equal-sized particles this is exact only in the continuum/near-continuum
regime; at the Knudsen numbers relevant here (Kn ~ 1-10 for 10-50 nm
particles) a full free-molecular kinetic treatment (e.g. Fuchs
interpolation) would shift the absolute kernel value.  The cleanroom/exhaust
*ratio* computed here is insensitive to that choice because the same kernel
is used on both sides; the *absolute* timescales should be read as
order-of-magnitude, not exact.

ISO 14644-1 concentration limits are only standardized down to a 0.1 um
(100 nm) particle-size threshold; the standard does not define a count for
particles smaller than that. Concentrations here therefore use the class
limit at 0.1 um as an upper-bound proxy for "particles at least this
numerous could be present," not a measurement of 10-50 nm particles
specifically. This is stated explicitly in every report this module emits.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

import numpy as np


# Air at approximately 20 degC and 1 atm -- matches
# simulation/aegis_radiation_force_feasibility.py for consistency.
ETA_SHEAR = 1.8e-5          # Pa*s
AIR_MEAN_FREE_PATH_M = 66e-9

KB = 1.380649e-23           # J/K
T_ROOM = 293.15              # K

DEFAULT_TARGET_DIAMETERS_NM = (10.0, 20.0, 50.0)
DEFAULT_ISO_CLASSES = (1, 2, 3, 5)
ISO_REFERENCE_DIAMETER_UM = 0.1  # finest threshold ISO 14644-1 standardizes

# Order-of-magnitude reference range for raw combustion/exhaust ultrafine
# particle number concentration, as used in the acoustic-agglomeration
# literature surveyed in docs/HYBRID_AGGLOMERATION_RESEARCH.md (diesel
# exhaust, coal-flue-gas studies). This is a representative range, not a
# single paper's exact measurement.
EXHAUST_REFERENCE_CONCENTRATION_PER_CM3 = (1.0e6, 1.0e9)


def _positive(value: float, name: str) -> float:
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


def iso_class_concentration_per_m3(
    iso_class: float, particle_diameter_um: float = ISO_REFERENCE_DIAMETER_UM
) -> float:
    """ISO 14644-1 maximum concentration Cn = 10^N * (0.1/D)^2.08.

    Officially valid only for particle_diameter_um >= 0.1; this raises for
    smaller sizes rather than silently extrapolating the power law below the
    standard's documented range.
    """

    iso_class = _positive(iso_class, "iso_class")
    particle_diameter_um = _positive(particle_diameter_um, "particle_diameter_um")
    if particle_diameter_um < 0.1:
        raise ValueError(
            "ISO 14644-1 does not define a concentration limit below 0.1 um; "
            "use the 0.1 um threshold as a proxy instead of extrapolating"
        )
    return (10.0 ** iso_class) * (0.1 / particle_diameter_um) ** 2.08


def cunningham_slip_correction(radius_m: float, mean_free_path_m: float = AIR_MEAN_FREE_PATH_M) -> float:
    radius_m = _positive(radius_m, "radius_m")
    knudsen = mean_free_path_m / radius_m
    return 1.0 + knudsen * (1.257 + 0.4 * np.exp(-1.1 / knudsen))


def brownian_diffusion_coefficient(radius_m: float, temperature_k: float = T_ROOM) -> float:
    radius_m = _positive(radius_m, "radius_m")
    temperature_k = _positive(temperature_k, "temperature_k")
    slip = cunningham_slip_correction(radius_m)
    return KB * temperature_k * slip / (6.0 * np.pi * ETA_SHEAR * radius_m)


def coagulation_kernel(radius_a_m: float, radius_b_m: float, temperature_k: float = T_ROOM) -> float:
    """Two-body Brownian (perikinetic) coagulation kernel, m^3/s."""

    radius_a_m = _positive(radius_a_m, "radius_a_m")
    radius_b_m = _positive(radius_b_m, "radius_b_m")
    diffusion_a = brownian_diffusion_coefficient(radius_a_m, temperature_k)
    diffusion_b = brownian_diffusion_coefficient(radius_b_m, temperature_k)
    return 4.0 * np.pi * (radius_a_m + radius_b_m) * (diffusion_a + diffusion_b)


def monodisperse_coagulation_kernel(radius_m: float, temperature_k: float = T_ROOM) -> float:
    return coagulation_kernel(radius_m, radius_m, temperature_k)


def collision_timescale_s(radius_m: float, number_concentration_per_m3: float, temperature_k: float = T_ROOM) -> float:
    """Mean time before a single particle undergoes one collision, 1/(K*n)."""

    number_concentration_per_m3 = _positive(number_concentration_per_m3, "number_concentration_per_m3")
    kernel = monodisperse_coagulation_kernel(radius_m, temperature_k)
    return 1.0 / (kernel * number_concentration_per_m3)


def population_half_life_s(radius_m: float, number_concentration_per_m3: float, temperature_k: float = T_ROOM) -> float:
    """Time for a monodisperse population to halve via self-coagulation.

    From dn/dt = -(1/2) K n^2, integrating gives n(t) = n0 / (1 + K n0 t / 2),
    so the half-life is t_1/2 = 2 / (K n0).
    """

    number_concentration_per_m3 = _positive(number_concentration_per_m3, "number_concentration_per_m3")
    kernel = monodisperse_coagulation_kernel(radius_m, temperature_k)
    return 2.0 / (kernel * number_concentration_per_m3)


def _seconds_to_human(seconds: float) -> str:
    if not np.isfinite(seconds):
        return "n/a"
    units = (
        ("s", 1.0),
        ("min", 60.0),
        ("hr", 3600.0),
        ("day", 86400.0),
        ("yr", 86400.0 * 365.25),
    )
    best_label, best_value = "s", seconds
    for label, factor in units:
        if seconds / factor >= 1.0:
            best_label, best_value = label, seconds / factor
    if best_label == "yr" and best_value > 1e6:
        return f"{best_value:.3e} yr"
    return f"{best_value:.3g} {best_label}"


def build_report(
    target_diameters_nm: Sequence[float] = DEFAULT_TARGET_DIAMETERS_NM,
    iso_classes: Sequence[float] = DEFAULT_ISO_CLASSES,
    exhaust_reference_per_cm3: Sequence[float] = EXHAUST_REFERENCE_CONCENTRATION_PER_CM3,
) -> dict:
    if not target_diameters_nm:
        raise ValueError("target_diameters_nm must not be empty")
    if not iso_classes:
        raise ValueError("iso_classes must not be empty")

    cleanroom_proxy_per_m3 = {
        str(iso_class): iso_class_concentration_per_m3(iso_class) for iso_class in iso_classes
    }

    diameter_results = []
    for diameter_nm in target_diameters_nm:
        radius_m = _positive(diameter_nm, "diameter_nm") * 1e-9 / 2.0
        kernel = monodisperse_coagulation_kernel(radius_m)

        cleanroom_results = []
        for iso_class in iso_classes:
            concentration_per_m3 = cleanroom_proxy_per_m3[str(iso_class)]
            half_life = population_half_life_s(radius_m, concentration_per_m3)
            cleanroom_results.append(
                {
                    "iso_class": iso_class,
                    "concentration_proxy_per_m3_at_0p1um": concentration_per_m3,
                    "collision_timescale_s": collision_timescale_s(radius_m, concentration_per_m3),
                    "population_half_life_s": half_life,
                    "population_half_life_human": _seconds_to_human(half_life),
                }
            )

        exhaust_results = []
        for concentration_per_cm3 in exhaust_reference_per_cm3:
            concentration_per_m3 = concentration_per_cm3 * 1e6
            half_life = population_half_life_s(radius_m, concentration_per_m3)
            exhaust_results.append(
                {
                    "concentration_per_cm3": concentration_per_cm3,
                    "collision_timescale_s": collision_timescale_s(radius_m, concentration_per_m3),
                    "population_half_life_s": half_life,
                    "population_half_life_human": _seconds_to_human(half_life),
                }
            )

        fastest_exhaust_half_life = min(r["population_half_life_s"] for r in exhaust_results)
        slowest_cleanroom_half_life = max(r["population_half_life_s"] for r in cleanroom_results)

        diameter_results.append(
            {
                "diameter_nm": diameter_nm,
                "radius_m": radius_m,
                "knudsen_number": AIR_MEAN_FREE_PATH_M / radius_m,
                "monodisperse_coagulation_kernel_m3_per_s": kernel,
                "cleanroom_results": cleanroom_results,
                "exhaust_reference_results": exhaust_results,
                "cleanroom_to_exhaust_slowdown_factor": (
                    slowest_cleanroom_half_life / fastest_exhaust_half_life
                ),
            }
        )

    return {
        "model": {
            "name": "brownian_coagulation_timescale_v1",
            "mechanism": "perikinetic (Brownian) coagulation, continuum kernel with Cunningham slip correction",
            "kernel_formula": "K(a,b) = 4*pi*(a+b)*(D(a)+D(b))",
        },
        "limitations": [
            "This is a baseline diffusion-limited estimate; it does not model any acoustic or electrostatic enhancement.",
            "No citable general-purpose acoustic-enhancement multiplier was found in the literature reviewed; none is applied.",
            "Continuum kernel with slip correction is used even though Kn>1 for 10-50 nm particles in air; a full free-molecular (Fuchs) treatment would shift absolute timescales.",
            "ISO 14644-1 concentration limits are standardized only at particle sizes >=0.1 um; the class limit at 0.1 um is used here as an upper-bound proxy for smaller target particles, not a measurement of them.",
            "The exhaust reference concentration is an order-of-magnitude literature range, not a single paper's exact measurement.",
            "This module answers a narrower question than 'will Aegis work': whether the coagulation mechanism itself is concentration-starved in a cleanroom relative to the environments where it has been validated.",
        ],
        "hardware_performance_validated": False,
        "target_diameter_results": diameter_results,
    }


def _print_text_report(report: dict) -> None:
    print(f"Model: {report['model']['name']} ({report['model']['mechanism']})")
    print(f"Kernel: {report['model']['kernel_formula']}\n")
    for result in report["target_diameter_results"]:
        print(f"--- Diameter {result['diameter_nm']:.0f} nm (Kn={result['knudsen_number']:.2f}) ---")
        for cleanroom in result["cleanroom_results"]:
            print(
                f"  ISO class {cleanroom['iso_class']:>2}: "
                f"n_proxy={cleanroom['concentration_proxy_per_m3_at_0p1um']:.3g} /m^3  "
                f"half-life={cleanroom['population_half_life_human']}"
            )
        for exhaust in result["exhaust_reference_results"]:
            print(
                f"  Exhaust ref  : n={exhaust['concentration_per_cm3']:.3g} /cm^3  "
                f"half-life={exhaust['population_half_life_human']}"
            )
        print(
            f"  Cleanroom (worst ISO class above) is "
            f"{result['cleanroom_to_exhaust_slowdown_factor']:.3g}x SLOWER than the "
            f"fastest exhaust reference case.\n"
        )
    print("Limitations:")
    for limitation in report["limitations"]:
        print(f"  - {limitation}")


def _plot_report(report: dict, output_path: str | None, show: bool) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.canvas.manager.set_window_title("Aegis Agglomeration Timescale vs. Concentration")

    diameters = [r["diameter_nm"] for r in report["target_diameter_results"]]
    for index, result in enumerate(report["target_diameter_results"]):
        cleanroom_x = [c["concentration_proxy_per_m3_at_0p1um"] / 1e6 for c in result["cleanroom_results"]]
        cleanroom_y = [c["population_half_life_s"] for c in result["cleanroom_results"]]
        exhaust_x = [e["concentration_per_cm3"] for e in result["exhaust_reference_results"]]
        exhaust_y = [e["population_half_life_s"] for e in result["exhaust_reference_results"]]
        color = plt.cm.viridis(index / max(len(diameters) - 1, 1))
        ax.loglog(cleanroom_x, cleanroom_y, "o--", color=color, label=f"{result['diameter_nm']:.0f}nm (cleanroom proxy)")
        ax.loglog(exhaust_x, exhaust_y, "s-", color=color, label=f"{result['diameter_nm']:.0f}nm (exhaust reference)")

    ax.set_xlabel("Number concentration (particles/cm^3)")
    ax.set_ylabel("Population half-life (s)")
    ax.set_title("Brownian coagulation half-life: cleanroom proxy vs. exhaust reference")
    ax.legend(fontsize=7)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()

    result_info = {"enabled": True, "output_path": None}
    if output_path:
        fig.savefig(output_path, dpi=150)
        result_info["output_path"] = output_path
    if show:
        plt.show()
    plt.close(fig)
    return result_info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diameters-nm", type=str, default=None, help="comma-separated particle diameters in nm")
    parser.add_argument("--iso-classes", type=str, default=None, help="comma-separated ISO 14644-1 classes")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", type=str, default=None, help="path to save the plot PNG")
    parser.add_argument("--no-show", action="store_true", help="do not open an interactive plot window")
    parser.add_argument("--no-plot", action="store_true", help="skip plot generation entirely")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    diameters = (
        [float(value) for value in args.diameters_nm.split(",")]
        if args.diameters_nm
        else list(DEFAULT_TARGET_DIAMETERS_NM)
    )
    iso_classes = (
        [float(value) for value in args.iso_classes.split(",")]
        if args.iso_classes
        else list(DEFAULT_ISO_CLASSES)
    )

    report = build_report(target_diameters_nm=diameters, iso_classes=iso_classes)

    if not args.no_plot:
        report["plot"] = _plot_report(report, args.output, show=not args.no_show)
    else:
        report["plot"] = {"enabled": False, "output_path": None}

    if args.format == "json":
        print(json.dumps(report, allow_nan=False, indent=2))
    else:
        _print_text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
