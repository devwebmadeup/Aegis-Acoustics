"""Air-only ideal-field estimate for acoustic trapping of aerosol particles.

This module intentionally models a *perfect one-dimensional standing wave* in
air.  At the stated peak pressure it is a maximum-gradient reference within
the inviscid 1-D assumptions, not a rigorous upper bound on other field
geometries or thermoviscous/kinetic mechanisms and not a model of an open
phased-array "shield".  Beam spreading, imperfect reflection, streaming,
background flow, particle deposition/re-entrainment, and
molecular-relaxation absorption are not included.

For a Rayleigh particle, the Bruus convention used here is

    F_max = 4*pi*Phi*k*a**3*E_ac
    Phi   = (1/3) * ((5*rho_tilde - 2)/(2*rho_tilde + 1) - kappa_tilde)

where ``p0`` is peak standing-wave pressure and
``E_ac = p0**2/(4*rho*c**2)``.  The corresponding node-to-antinode acoustic
potential barrier is

    Delta_U = 4*pi*abs(Phi)*a**3*E_ac.

``Delta_U/(k_B*T)`` is reported instead of treating ``k_B*T/d`` as a physical
Brownian force.  A chosen barrier target (10 kBT by default) is a design
criterion for equilibrium trapping robustness; it does not by itself prove
particle exclusion or low deposition in a flowing fab environment.
"""

from __future__ import annotations

import argparse
import json
import warnings
from typing import Iterable, Optional, Sequence

import numpy as np


# Air at approximately 20 degC and 1 atm.  This model is not parameterized for
# liquids or reduced-pressure process gases.
RHO_F = 1.2          # kg/m^3
C_F = 343.0          # m/s
ETA_SHEAR = 1.8e-5   # Pa*s
K_THERMAL = 0.026    # W/(m*K)
CP = 1005.0          # J/(kg*K)
GAMMA = 1.4
P_ATM = 101325.0     # Pa
KAPPA_F = 1.0 / (GAMMA * P_ATM)  # adiabatic compressibility, 1/Pa
AIR_MEAN_FREE_PATH_M = 66e-9

# Generic dense fab contamination particle (silica-like solid).
RHO_P = 2200.0       # kg/m^3
KAPPA_P = 2.67e-11   # 1/Pa

KB = 1.380649e-23    # J/K
T_ROOM = 293.15      # K

# Aggressive research-array assumptions.  Pressure is peak amplitude, not RMS.
P0_SOURCE = 3000.0
STANDOFF_M = 0.03
DEFAULT_BARRIER_KBT = 10.0
DEFAULT_FREQUENCIES_HZ = (40e3, 200e3, 1e6, 5e6)
DEFAULT_TARGET_DIAMETERS_NM = (10.0, 20.0, 50.0, 100.0, 150.0, 300.0)

# Compatibility only.  kBT/d is an energy-over-arbitrary-length heuristic, not
# an instantaneous Brownian force or a validated exclusion criterion.
SAFETY_FACTOR = 10.0

RAYLEIGH_KA_LIMIT = 0.1
PARTICLE_CONTINUUM_KN_LIMIT = 0.1
THIN_BOUNDARY_LAYER_LIMIT = 0.1  # max(delta_v, delta_t) / particle radius


def _finite_array(value, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if np.any(~np.isfinite(result)):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _positive_array(value, name: str, *, allow_zero: bool = False) -> np.ndarray:
    result = _finite_array(value, name)
    invalid = result < 0 if allow_zero else result <= 0
    if np.any(invalid):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {qualifier}")
    return result


def _scalar_or_array(original, result):
    return float(result) if np.ndim(original) == 0 else result


def gorkov_contrast_factor(
    rho_particle: float = RHO_P,
    rho_fluid: float = RHO_F,
    kappa_particle: float = KAPPA_P,
    kappa_fluid: float = KAPPA_F,
) -> float:
    """Return the dimensionless Gor'kov/Bruus acoustic contrast factor.

    The factor of one third is part of the Bruus convention paired with
    ``F_max = 4*pi*Phi*k*a**3*E_ac``.  Omitting it overstates force and
    potential depth by exactly three for the same material properties.
    """

    rho_particle = float(_positive_array(rho_particle, "rho_particle"))
    rho_fluid = float(_positive_array(rho_fluid, "rho_fluid"))
    kappa_particle = float(_positive_array(kappa_particle, "kappa_particle"))
    kappa_fluid = float(_positive_array(kappa_fluid, "kappa_fluid"))
    rho_tilde = rho_particle / rho_fluid
    kappa_tilde = kappa_particle / kappa_fluid
    return ((5.0 * rho_tilde - 2.0) / (2.0 * rho_tilde + 1.0) - kappa_tilde) / 3.0


def classical_attenuation_np_per_m(freq_hz):
    """Classical Stokes-Kirchhoff absorption in air, in Np/m.

    The expression is

    ``omega**2/(2*rho*c**3) * [4*eta/3 + (gamma-1)*K/Cp]``.

    Bulk viscosity and humidity-dependent O2/N2 molecular relaxation are
    omitted.  Consequently this is generally a lower bound on attenuation,
    especially at ultrasonic frequencies.
    """

    freq = _positive_array(freq_hz, "freq_hz", allow_zero=True)
    omega = 2.0 * np.pi * freq
    viscous_thermal = (
        (4.0 / 3.0) * ETA_SHEAR
        + K_THERMAL * (GAMMA - 1.0) / CP
    )
    result = omega**2 * viscous_thermal / (2.0 * RHO_F * C_F**3)
    return _scalar_or_array(freq_hz, result)


def acoustic_energy_density(p0):
    """Time-averaged acoustic energy density for peak pressure ``p0``."""

    pressure = _positive_array(p0, "p0", allow_zero=True)
    result = pressure**2 / (4.0 * RHO_F * C_F**2)
    return _scalar_or_array(p0, result)


def radiation_force(freq_hz, radius_m, p0):
    """Ideal maximum 1-D standing-wave radiation force in newtons.

    This is the Rayleigh, inviscid Gor'kov result at ``abs(sin(2*k*x))=1``.
    It is the maximum force amplitude within this model, not a rigorous bound
    across field geometries or a prediction for an open array.  Call
    :func:`model_validity` before interpreting a result.
    """

    freq = _positive_array(freq_hz, "freq_hz")
    radius = _positive_array(radius_m, "radius_m")
    pressure = _positive_array(p0, "p0", allow_zero=True)
    k = 2.0 * np.pi * freq / C_F
    result = (
        4.0
        * np.pi
        * gorkov_contrast_factor()
        * k
        * radius**3
        * acoustic_energy_density(pressure)
    )
    return float(result) if result.ndim == 0 else result


def pressure_after_standoff(freq_hz, p0, distance_m):
    """Peak pressure after classical absorption only.

    No geometrical spreading, aperture/directivity loss, reflection loss, or
    molecular-relaxation loss is applied, making the result optimistic.
    """

    freq = _positive_array(freq_hz, "freq_hz", allow_zero=True)
    pressure = _positive_array(p0, "p0", allow_zero=True)
    distance = _positive_array(distance_m, "distance_m", allow_zero=True)
    result = pressure * np.exp(-classical_attenuation_np_per_m(freq) * distance)
    return float(result) if result.ndim == 0 else result


def acoustic_potential_barrier(radius_m, p0):
    """Node-to-antinode Gor'kov potential barrier ``Delta_U`` in joules."""

    radius = _positive_array(radius_m, "radius_m")
    pressure = _positive_array(p0, "p0", allow_zero=True)
    result = (
        4.0
        * np.pi
        * abs(gorkov_contrast_factor())
        * radius**3
        * acoustic_energy_density(pressure)
    )
    return float(result) if result.ndim == 0 else result


def acoustic_potential_barrier_kbt(radius_m, p0, temperature_k: float = T_ROOM):
    """Return the ideal potential barrier normalized by thermal energy kBT."""

    temperature = float(_positive_array(temperature_k, "temperature_k"))
    return acoustic_potential_barrier(radius_m, p0) / (KB * temperature)


def min_diameter_for_barrier_ratio(
    p0_at_target,
    barrier_kbt: float = DEFAULT_BARRIER_KBT,
    temperature_k: float = T_ROOM,
):
    """Particle diameter needed for a selected ``Delta_U/(kBT)`` target.

    This inversion is independent of frequency at fixed target pressure.
    Frequency enters the report through propagation loss and validity checks.
    """

    pressure = _positive_array(p0_at_target, "p0_at_target")
    target = float(_positive_array(barrier_kbt, "barrier_kbt"))
    temperature = float(_positive_array(temperature_k, "temperature_k"))
    phi = abs(gorkov_contrast_factor())
    if phi == 0:
        raise ValueError("contrast factor is zero; no acoustic potential well exists")
    radius_cubed = target * KB * temperature / (
        4.0 * np.pi * phi * acoustic_energy_density(pressure)
    )
    result = 2.0 * np.cbrt(radius_cubed)
    return float(result) if result.ndim == 0 else result


def thermal_threshold_force(diameter_m, safety_factor: float = SAFETY_FACTOR):
    """Return the legacy ``safety_factor*kBT/d`` heuristic.

    .. warning::
       This is retained only for API compatibility.  Brownian motion is not an
       instantaneous force of this magnitude, and the arbitrary length ``d``
       does not define a validated particle-rejection criterion.  Use
       :func:`acoustic_potential_barrier_kbt` for an equilibrium energy metric.
    """

    warnings.warn(
        "kBT/d is a non-authoritative legacy heuristic; use the acoustic "
        "potential barrier in kBT instead",
        DeprecationWarning,
        stacklevel=2,
    )
    diameter = _positive_array(diameter_m, "diameter_m")
    safety = float(_positive_array(safety_factor, "safety_factor"))
    result = safety * KB * T_ROOM / diameter
    return _scalar_or_array(diameter_m, result)


def min_diameter_for_threshold(freq_hz, p0_at_target):
    """Legacy inversion of :func:`thermal_threshold_force`.

    This compatibility function is deliberately excluded from reports and
    plots because its force threshold is not a physical Brownian-force model.
    """

    warnings.warn(
        "the kBT/d threshold is non-authoritative; use "
        "min_diameter_for_barrier_ratio instead",
        DeprecationWarning,
        stacklevel=2,
    )
    freq = _positive_array(freq_hz, "freq_hz")
    pressure = _positive_array(p0_at_target, "p0_at_target")
    k = 2.0 * np.pi * freq / C_F
    coefficient = (
        4.0 * np.pi * gorkov_contrast_factor() * k
        * acoustic_energy_density(pressure)
    )
    if np.any(coefficient <= 0):
        raise ValueError("legacy threshold requires a positive contrast factor")
    radius_fourth = SAFETY_FACTOR * KB * T_ROOM / (2.0 * coefficient)
    result = 2.0 * radius_fourth**0.25
    return float(result) if result.ndim == 0 else result


def rayleigh_ka(freq_hz, diameter_m):
    """Dimensionless Rayleigh size parameter ``k*a``."""

    freq = _positive_array(freq_hz, "freq_hz")
    diameter = _positive_array(diameter_m, "diameter_m")
    result = 2.0 * np.pi * freq * (diameter / 2.0) / C_F
    return float(result) if result.ndim == 0 else result


def particle_knudsen_number(
    diameter_m, mean_free_path_m: float = AIR_MEAN_FREE_PATH_M
):
    """Particle Knudsen number, ``lambda/a = 2*lambda/d``."""

    diameter = _positive_array(diameter_m, "diameter_m")
    mean_free_path = float(_positive_array(mean_free_path_m, "mean_free_path_m"))
    result = 2.0 * mean_free_path / diameter
    return _scalar_or_array(diameter_m, result)


def viscous_boundary_layer_m(freq_hz):
    """Oscillatory viscous penetration depth in air."""

    freq = _positive_array(freq_hz, "freq_hz")
    result = np.sqrt(2.0 * ETA_SHEAR / (RHO_F * 2.0 * np.pi * freq))
    return _scalar_or_array(freq_hz, result)


def thermal_boundary_layer_m(freq_hz):
    """Oscillatory thermal penetration depth in air."""

    freq = _positive_array(freq_hz, "freq_hz")
    thermal_diffusivity = K_THERMAL / (RHO_F * CP)
    result = np.sqrt(2.0 * thermal_diffusivity / (2.0 * np.pi * freq))
    return _scalar_or_array(freq_hz, result)


def model_validity(freq_hz: float, diameter_m: float) -> dict:
    """Return explicit applicability indicators for one particle/frequency."""

    frequency = float(_positive_array(freq_hz, "freq_hz"))
    diameter = float(_positive_array(diameter_m, "diameter_m"))
    radius = diameter / 2.0
    ka = rayleigh_ka(frequency, diameter)
    kn = particle_knudsen_number(diameter)
    delta_v = viscous_boundary_layer_m(frequency)
    delta_t = thermal_boundary_layer_m(frequency)
    boundary_layer_ratio = max(delta_v, delta_t) / radius
    rayleigh_ok = ka <= RAYLEIGH_KA_LIMIT
    continuum_ok = kn <= PARTICLE_CONTINUUM_KN_LIMIT
    thin_boundary_ok = boundary_layer_ratio <= THIN_BOUNDARY_LAYER_LIMIT
    flags = []
    if not rayleigh_ok:
        flags.append(
            f"Rayleigh approximation warning: ka={ka:.3g} exceeds "
            f"{RAYLEIGH_KA_LIMIT:g}"
        )
    if not continuum_ok:
        flags.append(
            f"particle-scale continuum warning: Kn={kn:.3g} exceeds "
            f"{PARTICLE_CONTINUUM_KN_LIMIT:g}; slip/kinetic corrections are needed"
        )
    if not thin_boundary_ok:
        flags.append(
            "thermoviscous warning: max boundary-layer thickness / radius="
            f"{boundary_layer_ratio:.3g} exceeds {THIN_BOUNDARY_LAYER_LIMIT:g}; "
            "the inviscid contrast factor is not quantitatively reliable"
        )
    return {
        "rayleigh_ka": ka,
        "rayleigh_condition_met": rayleigh_ok,
        "particle_knudsen_number": kn,
        "particle_continuum_condition_met": continuum_ok,
        "viscous_boundary_layer_m": delta_v,
        "thermal_boundary_layer_m": delta_t,
        "max_boundary_layer_to_radius": boundary_layer_ratio,
        "thin_boundary_layer_condition_met": thin_boundary_ok,
        "inviscid_gorkov_conditions_met": (
            rayleigh_ok and continuum_ok and thin_boundary_ok
        ),
        "warnings": flags,
    }


def sanity_check_against_known_levitation(print_result: bool = True) -> dict:
    """Return a rough millimetre-EPS levitation order-of-magnitude check.

    This is not validation data: the assumed pressure and neglected foam
    compressibility are too approximate for that.  It merely catches gross
    unit/factor errors in the implementation.
    """

    frequency, pressure, radius, rho_bead = 40e3, 1000.0, 1.5e-3, 25.0
    phi = gorkov_contrast_factor(
        rho_particle=rho_bead,
        rho_fluid=RHO_F,
        kappa_particle=1e-30,  # explicitly negligible for this rough check
        kappa_fluid=KAPPA_F,
    )
    k = 2.0 * np.pi * frequency / C_F
    force = 4.0 * np.pi * phi * k * radius**3 * acoustic_energy_density(pressure)
    weight = (4.0 / 3.0) * np.pi * radius**3 * rho_bead * 9.81
    result = {
        "frequency_hz": frequency,
        "pressure_peak_pa": pressure,
        "diameter_m": 2.0 * radius,
        "radiation_force_n": force,
        "weight_n": weight,
        "force_to_weight_ratio": force / weight,
        "interpretation": "rough order-of-magnitude check only",
    }
    if print_result:
        print(
            "[Order-of-magnitude check] "
            f"40 kHz / {pressure:.0f} Pa / {2*radius*1e3:.1f} mm EPS: "
            f"Fmax={force*1e6:.1f} uN, weight={weight*1e6:.1f} uN, "
            f"ratio={force/weight:.2f}. Not validation data."
        )
    return result


def _float_list(values: Iterable[float], name: str) -> list[float]:
    array = _positive_array(list(values), name)
    if array.size == 0:
        raise ValueError(f"{name} must not be empty")
    return [float(value) for value in array]


def build_report(
    frequencies_hz: Sequence[float] = DEFAULT_FREQUENCIES_HZ,
    target_diameters_nm: Sequence[float] = DEFAULT_TARGET_DIAMETERS_NM,
    source_pressure_pa: float = P0_SOURCE,
    standoff_m: float = STANDOFF_M,
    barrier_kbt: float = DEFAULT_BARRIER_KBT,
    temperature_k: float = T_ROOM,
) -> dict:
    """Build a JSON-serializable feasibility report."""

    frequencies = _float_list(frequencies_hz, "frequencies_hz")
    diameters_nm = _float_list(target_diameters_nm, "target_diameters_nm")
    source_pressure = float(_positive_array(source_pressure_pa, "source_pressure_pa"))
    standoff = float(_positive_array(standoff_m, "standoff_m", allow_zero=True))
    barrier_target = float(_positive_array(barrier_kbt, "barrier_kbt"))
    temperature = float(_positive_array(temperature_k, "temperature_k"))

    frequency_results = []
    target_results = []
    validity_warnings = []
    for frequency in frequencies:
        alpha = classical_attenuation_np_per_m(frequency)
        pressure_target = pressure_after_standoff(
            frequency, source_pressure, standoff
        )
        minimum_diameter = min_diameter_for_barrier_ratio(
            pressure_target, barrier_target, temperature
        )
        minimum_diameter_validity = model_validity(frequency, minimum_diameter)
        frequency_results.append(
            {
                "frequency_hz": frequency,
                "wavelength_m": C_F / frequency,
                "classical_attenuation_np_per_m": alpha,
                "classical_attenuation_db_per_cm": alpha * 8.685889638 / 100.0,
                "classical_pressure_loss_db_at_standoff": (
                    alpha * standoff * 8.685889638
                ),
                "pressure_at_target_peak_pa": pressure_target,
                "min_diameter_for_barrier_m": minimum_diameter,
                "min_diameter_for_barrier_nm": minimum_diameter * 1e9,
                "min_diameter_within_model_validity": (
                    minimum_diameter_validity["inviscid_gorkov_conditions_met"]
                ),
                "min_diameter_validity": minimum_diameter_validity,
                "barrier_target_kbt": barrier_target,
            }
        )
        for diameter_nm in diameters_nm:
            diameter_m = diameter_nm * 1e-9
            radius_m = diameter_m / 2.0
            validity = model_validity(frequency, diameter_m)
            barrier_ratio = acoustic_potential_barrier_kbt(
                radius_m, pressure_target, temperature
            )
            meets_barrier_target = barrier_ratio >= barrier_target
            for message in validity["warnings"]:
                validity_warnings.append(
                    f"{frequency/1e3:g} kHz, {diameter_nm:g} nm: {message}"
                )
            target_results.append(
                {
                    "frequency_hz": frequency,
                    "diameter_nm": diameter_nm,
                    "pressure_at_target_peak_pa": pressure_target,
                    "max_radiation_force_n": radiation_force(
                        frequency, radius_m, pressure_target
                    ),
                    "potential_barrier_j": acoustic_potential_barrier(
                        radius_m, pressure_target
                    ),
                    "potential_barrier_kbt": barrier_ratio,
                    "meets_selected_barrier_target": meets_barrier_target,
                    "passes_barrier_and_applicability_checks": (
                        meets_barrier_target
                        and validity["inviscid_gorkov_conditions_met"]
                    ),
                    "validity": validity,
                }
            )

    limitations = [
        "Air-only material properties near 20 degC and 1 atm are used.",
        "The field is a perfect 1-D standing wave at its maximum gradient; this is an optimistic reference at the stated pressure, not a rigorous bound or an open-array shield simulation.",
        "Propagation includes classical absorption only; spreading, reflection loss, and humidity-dependent molecular relaxation are omitted.",
        "Streaming, background flow, drag/slip dynamics, Brownian trajectories, deposition, and re-entrainment are omitted.",
        "Delta_U/kBT describes an ideal equilibrium well; the selected barrier target is a design criterion, not proof of exclusion performance.",
        f"Rayleigh results should have ka <= {RAYLEIGH_KA_LIMIT:g}; particle-continuum results should have Kn <= {PARTICLE_CONTINUUM_KN_LIMIT:g}.",
        "When acoustic boundary layers are not thin relative to the particle, a thermoviscous scattering model must replace the inviscid contrast factor.",
    ]
    return {
        "model": {
            "name": "air_1d_standing_wave_ideal_field_estimate",
            "contrast_factor_convention": "Bruus Phi=(f1/3)+(f2/2)",
            "gorkov_contrast_factor": gorkov_contrast_factor(),
            "pressure_convention": "peak standing-wave pressure amplitude",
            "attenuation_model": "classical Stokes-Kirchhoff lower bound",
        },
        "inputs": {
            "source_pressure_peak_pa": source_pressure,
            "standoff_m": standoff,
            "temperature_k": temperature,
            "barrier_target_kbt": barrier_target,
            "frequencies_hz": frequencies,
            "target_diameters_nm": diameters_nm,
        },
        "frequency_results": frequency_results,
        "target_results": target_results,
        "validity_warnings": validity_warnings,
        "limitations": limitations,
        "hardware_performance_validated": False,
        "order_of_magnitude_check": sanity_check_against_known_levitation(False),
    }


def format_report_table(report: dict) -> str:
    """Format a report as human-readable plain-text tables."""

    inputs = report["inputs"]
    lines = [
        "AIR-ONLY IDEAL 1-D STANDING-WAVE ESTIMATE",
        (
            f"Source peak pressure: {inputs['source_pressure_peak_pa']:.6g} Pa | "
            f"standoff: {inputs['standoff_m']*100:.3g} cm | "
            f"selected barrier: {inputs['barrier_target_kbt']:.3g} kBT"
        ),
        "",
        "Frequency summary",
        (
            f"{'Freq':>10} | {'classical dB/cm':>15} | "
            f"{'target p (Pa)':>13} | {'min diameter*':>15} | {'valid':>5}"
        ),
        "-" * 71,
    ]
    for row in report["frequency_results"]:
        lines.append(
            f"{row['frequency_hz']/1e3:>8.3g} kHz | "
            f"{row['classical_attenuation_db_per_cm']:>15.4g} | "
            f"{row['pressure_at_target_peak_pa']:>13.4g} | "
            f"{row['min_diameter_for_barrier_nm']:>11.4g} nm | "
            f"{'yes' if row['min_diameter_within_model_validity'] else 'NO':>5}"
        )

    lines.extend(
        [
            "",
            "* min diameter is an algebraic extrapolation when valid=NO.",
            "",
            "Requested particle diameters",
            (
                f"{'Freq':>10} | {'diameter':>10} | {'Fmax (N)':>11} | "
                f"{'DeltaU/kBT':>11} | {'ka':>9} | {'Kn':>9} | {'valid*':>6}"
            ),
            "-" * 87,
        ]
    )
    for row in report["target_results"]:
        validity = row["validity"]
        lines.append(
            f"{row['frequency_hz']/1e3:>8.3g} kHz | "
            f"{row['diameter_nm']:>7.4g} nm | "
            f"{row['max_radiation_force_n']:>11.3e} | "
            f"{row['potential_barrier_kbt']:>11.3e} | "
            f"{validity['rayleigh_ka']:>9.2e} | "
            f"{validity['particle_knudsen_number']:>9.2e} | "
            f"{'yes' if validity['inviscid_gorkov_conditions_met'] else 'NO':>6}"
        )

    lines.extend(
        [
            "",
            "* valid requires the Rayleigh, particle-continuum, and thin-boundary-layer checks all to pass.",
            "Limitations / warnings",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    if report["validity_warnings"]:
        lines.append("Target-specific validity warnings")
        lines.extend(f"- {item}" for item in report["validity_warnings"])
    return "\n".join(lines)


def plot_report(
    report: dict,
    output_path: Optional[str],
    *,
    show: bool,
) -> None:
    """Create the potential-barrier and attenuation plot."""

    # Backend selection must precede pyplot import for headless environments.
    import matplotlib

    if not show:
        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    inputs = report["inputs"]
    frequencies = inputs["frequencies_hz"]
    diameters_nm = np.logspace(1.0, 4.3, 400)
    radii_m = diameters_nm * 1e-9 / 2.0

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    manager = getattr(fig.canvas, "manager", None)
    if manager is not None and hasattr(manager, "set_window_title"):
        manager.set_window_title("Aegis air standing-wave ideal-field check")

    ax = axes[0]
    for frequency in frequencies:
        pressure_target = pressure_after_standoff(
            frequency,
            inputs["source_pressure_peak_pa"],
            inputs["standoff_m"],
        )
        ratios = acoustic_potential_barrier_kbt(
            radii_m, pressure_target, inputs["temperature_k"]
        )
        ax.loglog(diameters_nm, ratios, label=f"{frequency/1e3:g} kHz")
    ax.axhline(1.0, color="0.35", ls=":", label="1 kBT")
    ax.axhline(
        inputs["barrier_target_kbt"],
        color="black",
        ls="--",
        label=f"selected {inputs['barrier_target_kbt']:g} kBT",
    )
    ax.axvspan(10.0, 50.0, color="red", alpha=0.12, label="10-50 nm target")
    ax.set_xlabel("Particle diameter (nm)")
    ax.set_ylabel("Ideal potential barrier, Delta U / kBT")
    ax.set_title(
        "Perfect standing-wave well depth\n"
        f"after {inputs['standoff_m']*100:g} cm classical attenuation"
    )
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)

    ax2 = axes[1]
    frequency_sweep = np.logspace(4, 7, 300)
    attenuation_db_cm = (
        classical_attenuation_np_per_m(frequency_sweep) * 8.685889638 / 100.0
    )
    ax2.loglog(frequency_sweep / 1e3, attenuation_db_cm)
    ax2.set_xlabel("Frequency (kHz)")
    ax2.set_ylabel("Classical absorption (dB/cm)")
    ax2.set_title(
        "Stokes-Kirchhoff absorption only\n"
        "lower bound; molecular relaxation omitted"
    )
    ax2.grid(True, which="both", alpha=0.3)

    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150)
    if show:
        plt.show()
    else:
        plt.close(fig)


def _comma_separated_floats(value: str) -> list[float]:
    try:
        result = [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not result or any(not np.isfinite(item) or item <= 0 for item in result):
        raise argparse.ArgumentTypeError("values must be finite positive numbers")
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Air-only ideal standing-wave reference calculation. "
            "It is not an open-array shield simulation."
        )
    )
    parser.add_argument(
        "--frequencies-khz",
        type=_comma_separated_floats,
        default=[value / 1e3 for value in DEFAULT_FREQUENCIES_HZ],
        metavar="KHz,...",
        help="comma-separated frequencies in kHz",
    )
    parser.add_argument(
        "--diameters-nm",
        type=_comma_separated_floats,
        default=list(DEFAULT_TARGET_DIAMETERS_NM),
        metavar="NM,...",
        help="comma-separated target particle diameters in nm",
    )
    parser.add_argument(
        "--source-pressure",
        type=float,
        default=P0_SOURCE,
        metavar="PA",
        help="peak standing-wave pressure assumed at the source face",
    )
    parser.add_argument(
        "--standoff",
        type=float,
        default=STANDOFF_M,
        metavar="M",
        help="source-to-target distance in metres",
    )
    parser.add_argument(
        "--barrier-kbt",
        type=float,
        default=DEFAULT_BARRIER_KBT,
        help="selected ideal potential-well target in kBT",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="stdout report format",
    )
    parser.add_argument(
        "--output",
        default="aegis_radiation_force_feasibility.png",
        metavar="PATH",
        help="plot output path",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="use a headless backend and do not open a plot window",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="skip plot generation (useful for machine-readable CI output)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    report = build_report(
        frequencies_hz=[value * 1e3 for value in args.frequencies_khz],
        target_diameters_nm=args.diameters_nm,
        source_pressure_pa=args.source_pressure,
        standoff_m=args.standoff,
        barrier_kbt=args.barrier_kbt,
    )
    report["plot"] = {
        "enabled": not args.no_plot,
        "output_path": args.output if not args.no_plot else None,
        "shown": not args.no_show and not args.no_plot,
    }

    if not args.no_plot:
        plot_report(report, args.output, show=not args.no_show)

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(format_report_table(report))
        if not args.no_plot and args.output:
            print(f"\nSaved plot: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
