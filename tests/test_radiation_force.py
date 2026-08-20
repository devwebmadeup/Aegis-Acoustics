"""Regression tests for the air standing-wave ideal-field calculation."""

import importlib.util
import io
import json
import math
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from pathlib import Path

from simulation import aegis_radiation_force_feasibility as model


class RadiationForcePhysicsTests(unittest.TestCase):
    def test_bruus_contrast_factor_includes_one_third(self):
        rho_tilde = model.RHO_P / model.RHO_F
        kappa_tilde = model.KAPPA_P / model.KAPPA_F
        expected = (
            (5.0 * rho_tilde - 2.0) / (2.0 * rho_tilde + 1.0)
            - kappa_tilde
        ) / 3.0
        self.assertAlmostEqual(model.gorkov_contrast_factor(), expected, places=14)
        self.assertGreater(model.gorkov_contrast_factor(), 0.0)

    def test_stokes_kirchhoff_prefactor_and_frequency_scaling(self):
        frequency = 200e3
        omega = 2.0 * math.pi * frequency
        bracket = (
            (4.0 / 3.0) * model.ETA_SHEAR
            + model.K_THERMAL * (model.GAMMA - 1.0) / model.CP
        )
        expected = (
            omega**2 * bracket / (2.0 * model.RHO_F * model.C_F**3)
        )
        actual = model.classical_attenuation_np_per_m(frequency)
        self.assertAlmostEqual(actual, expected, places=14)
        self.assertAlmostEqual(
            model.classical_attenuation_np_per_m(2.0 * frequency) / actual,
            4.0,
            places=12,
        )

    def test_pressure_amplitude_uses_exponential_attenuation(self):
        frequency = 1e6
        source_pressure = 3000.0
        distance = 0.03
        alpha = model.classical_attenuation_np_per_m(frequency)
        expected = source_pressure * math.exp(-alpha * distance)
        self.assertAlmostEqual(
            model.pressure_after_standoff(frequency, source_pressure, distance),
            expected,
            places=12,
        )

    def test_force_and_node_to_antinode_barrier_are_consistent(self):
        frequency = 200e3
        radius = 250e-9
        pressure = 1500.0
        wave_number = 2.0 * math.pi * frequency / model.C_F
        force_max = model.radiation_force(frequency, radius, pressure)
        barrier = model.acoustic_potential_barrier(radius, pressure)
        self.assertAlmostEqual(barrier, force_max / wave_number, places=28)

    def test_barrier_scales_with_particle_volume(self):
        pressure = 3000.0
        small = model.acoustic_potential_barrier_kbt(25e-9, pressure)
        large = model.acoustic_potential_barrier_kbt(50e-9, pressure)
        self.assertAlmostEqual(large / small, 8.0, places=12)

    def test_barrier_diameter_inversion(self):
        pressure = 2400.0
        target_kbt = 10.0
        diameter = model.min_diameter_for_barrier_ratio(pressure, target_kbt)
        recovered = model.acoustic_potential_barrier_kbt(
            diameter / 2.0, pressure
        )
        self.assertAlmostEqual(recovered, target_kbt, places=11)

    def test_legacy_kbt_over_d_api_is_explicitly_deprecated(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = model.thermal_threshold_force(100e-9)
        self.assertGreater(value, 0.0)
        self.assertEqual(len(caught), 1)
        self.assertIn("non-authoritative", str(caught[0].message))


class ModelValidityTests(unittest.TestCase):
    def test_default_target_diameters_match_project_validation_steps(self):
        self.assertEqual(
            model.DEFAULT_TARGET_DIAMETERS_NM,
            (10.0, 20.0, 50.0, 100.0, 150.0, 300.0),
        )

    def test_nanoparticle_flags_continuum_and_thermoviscous_limits(self):
        validity = model.model_validity(1e6, 10e-9)
        self.assertTrue(validity["rayleigh_condition_met"])
        self.assertFalse(validity["particle_continuum_condition_met"])
        self.assertFalse(validity["thin_boundary_layer_condition_met"])
        warning_text = " ".join(validity["warnings"])
        self.assertIn("continuum", warning_text)
        self.assertIn("thermoviscous", warning_text)

    def test_large_particle_flags_rayleigh_limit(self):
        validity = model.model_validity(1e6, 20e-6)
        self.assertGreater(validity["rayleigh_ka"], model.RAYLEIGH_KA_LIMIT)
        self.assertFalse(validity["rayleigh_condition_met"])
        self.assertTrue(
            any("Rayleigh" in message for message in validity["warnings"])
        )

    def test_report_has_per_diameter_results_and_is_json_serializable(self):
        report = model.build_report(
            frequencies_hz=[40e3, 200e3],
            target_diameters_nm=[10.0, 50.0],
        )
        self.assertEqual(len(report["frequency_results"]), 2)
        self.assertEqual(len(report["target_results"]), 4)
        self.assertIn("ideal_field_estimate", report["model"]["name"])
        self.assertFalse(
            report["frequency_results"][0]["min_diameter_within_model_validity"]
        )
        self.assertFalse(report["hardware_performance_validated"])
        self.assertTrue(report["validity_warnings"])
        json.dumps(report, allow_nan=False)

    def test_barrier_pass_does_not_override_failed_model_applicability(self):
        report = model.build_report(
            frequencies_hz=[40e3],
            target_diameters_nm=[150.0],
        )
        result = report["target_results"][0]
        self.assertTrue(result["meets_selected_barrier_target"])
        self.assertFalse(result["validity"]["inviscid_gorkov_conditions_met"])
        self.assertFalse(result["passes_barrier_and_applicability_checks"])

    def test_invalid_inputs_fail_loudly(self):
        with self.assertRaises(ValueError):
            model.radiation_force(0.0, 10e-9, 1000.0)
        with self.assertRaises(ValueError):
            model.build_report(source_pressure_pa=-1.0)


class CommandLineTests(unittest.TestCase):
    def test_json_stdout_without_plot_is_machine_readable(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = model.main(
                [
                    "--no-show",
                    "--no-plot",
                    "--format",
                    "json",
                    "--frequencies-khz",
                    "40",
                    "--diameters-nm",
                    "10,50",
                ]
            )
        self.assertEqual(status, 0)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["plot"]["enabled"])
        self.assertEqual(len(report["target_results"]), 2)

    @unittest.skipUnless(
        importlib.util.find_spec("matplotlib") is not None,
        "matplotlib is not installed",
    )
    def test_no_show_writes_requested_plot(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "headless.png"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = model.main(
                    [
                        "--no-show",
                        "--format",
                        "json",
                        "--output",
                        str(output_path),
                        "--frequencies-khz",
                        "40",
                        "--diameters-nm",
                        "50",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertTrue(output_path.is_file())
            self.assertGreater(output_path.stat().st_size, 0)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["plot"]["output_path"], str(output_path))


if __name__ == "__main__":
    unittest.main()
