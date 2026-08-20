"""Deterministic tests for the ToF/phase Monte Carlo sensitivity model."""

import contextlib
import io
import json
import math
import unittest

from simulation import aegis_phase_uncertainty as uncertainty


class PhaseUncertaintyMonteCarloTests(unittest.TestCase):
    def test_zero_noise_recovers_speed_and_arrival_phase(self):
        result = uncertainty.run_phase_uncertainty_monte_carlo(
            trials=8,
            seed=7,
            timestamp_noise_std_s=0.0,
            distance_noise_std_m=0.0,
            phase_error_budget_rad=1.0e-9,
        )

        self.assertEqual(result["configuration"]["array"]["channels"], 256)
        self.assertEqual(result["trial_accounting"]["valid"], 8)
        self.assertEqual(result["trial_accounting"]["invalid"], 0)
        self.assertLess(
            result["sound_speed_error"]["absolute_m_s"]["maximum"], 1.0e-9
        )
        self.assertLess(
            result["arrival_phase_error"]["trial_max_absolute_rad"]["maximum"],
            1.0e-9,
        )
        self.assertTrue(result["acceptance"]["passed"])
        expected_tick_s = 1.0e-9 / (2.0 * math.pi * 40_000.0)
        self.assertAlmostEqual(
            result["phase_quantization_design_bound"][
                "maximum_tick_s_if_full_budget_is_allocated_to_quantization"
            ],
            expected_tick_s,
            places=20,
        )
        self.assertFalse(
            result["phase_quantization_design_bound"][
                "quantization_simulated_in_monte_carlo"
            ]
        )

    def test_seed_makes_noisy_result_exactly_reproducible(self):
        arguments = {
            "trials": 40,
            "seed": 123456,
            "timestamp_noise_std_s": 120.0e-9,
            "distance_noise_std_m": 75.0e-6,
        }
        first = uncertainty.run_phase_uncertainty_monte_carlo(**arguments)
        second = uncertainty.run_phase_uncertainty_monte_carlo(**arguments)

        self.assertEqual(first, second)
        self.assertGreater(
            first["sound_speed_error"]["absolute_m_s"]["p95"], 0.0
        )
        self.assertGreater(
            first["arrival_phase_error"]["trial_max_absolute_rad"]["p95"],
            0.0,
        )

    def test_documented_default_seeded_result_is_golden(self):
        result = uncertainty.run_phase_uncertainty_monte_carlo(
            trials=2_000,
            seed=20_260_820,
            timestamp_noise_std_s=100.0e-9,
            distance_noise_std_m=50.0e-6,
        )

        self.assertEqual(result["trial_accounting"]["invalid"], 0)
        self.assertAlmostEqual(
            result["arrival_phase_error"]["trial_max_absolute_rad"]["p95"],
            0.007093217999876836,
            places=15,
        )
        self.assertFalse(result["hardware_accuracy_validated"])

    def test_summaries_have_ordered_required_percentiles(self):
        result = uncertainty.run_phase_uncertainty_monte_carlo(trials=60, seed=9)
        for summary in (
            result["sound_speed_error"]["absolute_m_s"],
            result["sound_speed_error"]["absolute_fraction"],
            result["arrival_phase_error"]["trial_max_absolute_rad"],
            result["arrival_phase_error"]["all_channel_absolute_rad"],
        ):
            self.assertLessEqual(summary["p50"], summary["p95"])
            self.assertLessEqual(summary["p95"], summary["p99"])
            self.assertLessEqual(summary["p99"], summary["maximum"])
        self.assertEqual(
            result["arrival_phase_error"]["channel_observations"], 60 * 256
        )

    def test_tight_budget_fails_without_claiming_hardware_validation(self):
        result = uncertainty.run_phase_uncertainty_monte_carlo(
            trials=30,
            seed=11,
            timestamp_noise_std_s=100.0e-9,
            distance_noise_std_m=50.0e-6,
            phase_error_budget_rad=1.0e-12,
        )

        self.assertFalse(result["acceptance"]["within_phase_budget"])
        self.assertFalse(result["acceptance"]["passed"])
        self.assertFalse(result["hardware_accuracy_validated"])
        self.assertFalse(result["noise_parameters_measured_on_aegis_hardware"])
        self.assertEqual(
            result["acceptance"]["threshold_origin"],
            "user-supplied engineering criterion",
        )
        self.assertIn(
            "Hardware accuracy not validated", result["hardware_accuracy_note"]
        )
        self.assertTrue(
            any(
                "spatially uniform" in limitation
                for limitation in result["model_limitations"]
            )
        )

    def test_explicit_input_validation(self):
        invalid_calls = (
            {"trials": 0},
            {"trials": True},
            {"seed": True},
            {"timestamp_noise_std_s": -1.0},
            {"distance_noise_std_m": math.nan},
            {"true_sound_speed_m_s": 0.0},
            {"time_offset_s": -1.0},
            {"frequency_hz": 0.0},
            {"phase_error_budget_rad": 0.0},
            {"calibration_distances_m": (0.1,)},
            {"calibration_distances_m": (0.1, 0.1)},
            {"target_m": (0.0, 0.0)},
        )
        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                with self.assertRaises((TypeError, ValueError)):
                    uncertainty.run_phase_uncertainty_monte_carlo(**arguments)


class PhaseUncertaintyCliTests(unittest.TestCase):
    def test_json_cli_is_machine_readable_and_deterministic(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = uncertainty.main(
                (
                    "--trials",
                    "12",
                    "--seed",
                    "42",
                    "--timestamp-noise-std-s",
                    "1e-7",
                    "--distance-noise-std-m",
                    "5e-5",
                    "--json",
                )
            )
        document = json.loads(stdout.getvalue())

        self.assertEqual(status, 0)
        self.assertEqual(document["configuration"]["seed"], 42)
        self.assertEqual(document["configuration"]["array"]["channels"], 256)
        self.assertIn("p99", document["sound_speed_error"]["absolute_m_s"])
        self.assertFalse(document["hardware_accuracy_validated"])

    def test_fail_on_budget_returns_status_two(self):
        with contextlib.redirect_stdout(io.StringIO()):
            status = uncertainty.main(
                (
                    "--trials",
                    "12",
                    "--seed",
                    "42",
                    "--phase-error-budget-rad",
                    "1e-12",
                    "--fail-on-budget",
                )
            )
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
