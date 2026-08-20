"""Deterministic tests for the Aegis phase-calibration reference module."""

import contextlib
import io
import json
import math
import unittest

from simulation import aegis_phase_calibration as calibration


class PlanarArrayTests(unittest.TestCase):
    def test_centred_rectangular_coordinates_are_row_major_and_si_scaled(self):
        coordinates = calibration.planar_array_coordinates(
            rows=2,
            columns=3,
            pitch_x_m=0.010,
            pitch_y_m=0.020,
            origin_m=(1.0, 2.0, 3.0),
        )
        self.assertEqual(
            coordinates,
            (
                (0.99, 1.99, 3.0),
                (1.00, 1.99, 3.0),
                (1.01, 1.99, 3.0),
                (0.99, 2.01, 3.0),
                (1.00, 2.01, 3.0),
                (1.01, 2.01, 3.0),
            ),
        )

    def test_array_input_validation(self):
        with self.assertRaises(TypeError):
            calibration.planar_array_coordinates(True, 16, 0.004)
        with self.assertRaises(ValueError):
            calibration.planar_array_coordinates(0, 16, 0.004)
        with self.assertRaises(ValueError):
            calibration.planar_array_coordinates(16, 16, -0.004)
        with self.assertRaises(ValueError):
            calibration.planar_array_coordinates(16, 16, 0.004, origin_m=(0, 0))


class TimeOfFlightTests(unittest.TestCase):
    def test_exact_tof_fit_recovers_speed_and_shared_offset(self):
        expected_speed_m_s = 343.25
        expected_offset_s = 23.0e-6
        distances_m = (0.04, 0.09, 0.14, 0.19)
        times_s = tuple(
            expected_offset_s + distance / expected_speed_m_s
            for distance in distances_m
        )

        result = calibration.estimate_sound_speed_from_tof(distances_m, times_s)

        self.assertAlmostEqual(result.sound_speed_m_s, expected_speed_m_s, places=10)
        self.assertAlmostEqual(result.time_offset_s, expected_offset_s, places=15)
        self.assertLess(result.rms_residual_s, 1e-18)
        self.assertEqual(result.sample_count, 4)
        self.assertTrue(result.fit_time_offset)

    def test_origin_constrained_tof_fit(self):
        result = calibration.estimate_sound_speed_from_tof(
            (0.10, 0.20),
            (0.10 / 350.0, 0.20 / 350.0),
            fit_time_offset=False,
        )
        self.assertAlmostEqual(result.sound_speed_m_s, 350.0, places=12)
        self.assertEqual(result.time_offset_s, 0.0)

    def test_tof_input_validation(self):
        with self.assertRaises(ValueError):
            calibration.estimate_sound_speed_from_tof((0.1,), (0.001,))
        with self.assertRaises(ValueError):
            calibration.estimate_sound_speed_from_tof((0.1, 0.1), (0.001, 0.002))
        with self.assertRaises(ValueError):
            calibration.estimate_sound_speed_from_tof((0.1, 0.2), (0.001,))
        with self.assertRaises(ValueError):
            calibration.estimate_sound_speed_from_tof((0.1, -0.2), (0.001, 0.002))
        with self.assertRaises(TypeError):
            calibration.estimate_sound_speed_from_tof((0.1,), (0.001,), fit_time_offset=1)


class DelayAndPhaseTests(unittest.TestCase):
    def test_phase_wrapping(self):
        self.assertEqual(calibration.wrap_phase_rad(0.0), 0.0)
        self.assertAlmostEqual(calibration.wrap_phase_rad(-math.pi / 2), 1.5 * math.pi)
        self.assertAlmostEqual(calibration.wrap_phase_rad(5 * math.pi), math.pi)
        with self.assertRaises(ValueError):
            calibration.wrap_phase_rad(math.inf)

    def test_delays_align_direct_path_arrival_phase(self):
        coordinates = ((-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        target = (0.0, 0.0, 1.0)
        solution = calibration.calculate_focus_solution(
            coordinates,
            target,
            sound_speed_m_s=1.0,
            frequency_hz=0.25,
        )

        expected_centre_delay = math.sqrt(2.0) - 1.0
        self.assertAlmostEqual(solution.delay_s[0], 0.0)
        self.assertAlmostEqual(solution.delay_s[1], expected_centre_delay)
        self.assertAlmostEqual(solution.delay_s[2], 0.0)

        omega = 2.0 * math.pi * solution.frequency_hz
        arrival_phases = tuple(
            (phase - omega * tof) % (2.0 * math.pi)
            for phase, tof in zip(solution.phase_rad, solution.propagation_time_s)
        )
        for arrival_phase in arrival_phases[1:]:
            circular_difference = math.atan2(
                math.sin(arrival_phase - arrival_phases[0]),
                math.cos(arrival_phase - arrival_phases[0]),
            )
            self.assertAlmostEqual(circular_difference, 0.0, places=14)

    def test_focus_input_validation(self):
        with self.assertRaises(ValueError):
            calibration.calculate_focus_solution([], (0, 0, 1), 343.0, 40_000.0)
        with self.assertRaises(ValueError):
            calibration.calculate_focus_solution([(0, 0, 0)], (0, 0, 0), 343.0, 40_000.0)
        with self.assertRaises(ValueError):
            calibration.calculate_focus_solution([(0, 0, 0)], (0, 0, 1), 0.0, 40_000.0)
        with self.assertRaises(ValueError):
            calibration.calculate_focus_solution([(0, 0, 0)], (0, 0, 1), 343.0, math.nan)


class ExamplesAndBenchmarkTests(unittest.TestCase):
    def test_air_n2_he_examples_are_exact_synthetic_recoveries(self):
        result = calibration.run_gas_examples()
        self.assertEqual(result["array"]["channels"], 256)
        examples = result["examples"]
        self.assertEqual([example["gas"] for example in examples], ["air", "n2", "he"])
        for example in examples:
            self.assertAlmostEqual(
                example["tof_estimated_speed_m_s"],
                example["ideal_reference_speed_m_s"],
                places=9,
            )
            self.assertAlmostEqual(example["fitted_time_offset_s"], 18e-6, places=15)
            self.assertLess(example["max_arrival_phase_error_rad"], 1e-12)
        self.assertFalse(result["physical_accuracy_validated"])

    def test_benchmark_statistics_and_budget_are_deterministic_with_fake_timer(self):
        timestamps_ns = iter((0, 1_000_000, 2_000_000, 4_000_000, 5_000_000, 9_000_000))
        result = calibration.benchmark_256_channel_phase_update(
            iterations=3,
            warmup_iterations=0,
            budget_ms=3.9,
            _timer_ns=lambda: next(timestamps_ns),
        )

        self.assertEqual(result["channels"], 256)
        self.assertEqual(result["timing"]["minimum_ms"], 1.0)
        self.assertEqual(result["timing"]["median_ms"], 2.0)
        self.assertAlmostEqual(result["timing"]["p95_ms"], 3.8)
        self.assertAlmostEqual(result["timing"]["p99_ms"], 3.96)
        self.assertEqual(result["timing"]["maximum_ms"], 4.0)
        self.assertTrue(result["within_budget"])
        self.assertFalse(result["all_samples_within_budget"])
        self.assertFalse(result["physical_accuracy_validated"])

    def test_examples_cli_emits_valid_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = calibration.main(("examples", "--json"))
        document = json.loads(stdout.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(document["array"]["channels"], 256)
        self.assertEqual(len(document["examples"]), 3)

    def test_benchmark_input_validation(self):
        with self.assertRaises(ValueError):
            calibration.benchmark_256_channel_phase_update(iterations=0)
        with self.assertRaises(ValueError):
            calibration.benchmark_256_channel_phase_update(warmup_iterations=-1)
        with self.assertRaises(ValueError):
            calibration.benchmark_256_channel_phase_update(budget_ms=0.0)


if __name__ == "__main__":
    unittest.main()
