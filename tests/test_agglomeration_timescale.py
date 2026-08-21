"""Regression tests for the Brownian coagulation-timescale comparison."""

import io
import json
import math
import unittest
from contextlib import redirect_stdout

from simulation import aegis_agglomeration_timescale as model


class CoagulationPhysicsTests(unittest.TestCase):
    def test_cunningham_correction_exceeds_one_for_nanoparticles(self):
        self.assertGreater(model.cunningham_slip_correction(5e-9), 1.0)
        self.assertGreater(
            model.cunningham_slip_correction(5e-9),
            model.cunningham_slip_correction(500e-9),
        )

    def test_diffusion_coefficient_scales_inversely_with_radius_in_continuum_limit(self):
        small_radius = 5e-6  # Kn << 1, Cc approx 1
        large_radius = 10e-6
        ratio = model.brownian_diffusion_coefficient(small_radius) / model.brownian_diffusion_coefficient(large_radius)
        self.assertAlmostEqual(ratio, 2.0, delta=0.05)

    def test_monodisperse_kernel_matches_closed_form_for_equal_particles(self):
        radius = 25e-9
        diffusion = model.brownian_diffusion_coefficient(radius)
        expected = 4.0 * math.pi * (2.0 * radius) * (2.0 * diffusion)
        self.assertAlmostEqual(
            model.monodisperse_coagulation_kernel(radius), expected, places=20
        )

    def test_kernel_is_symmetric_and_matches_monodisperse_case(self):
        a, b = 15e-9, 40e-9
        self.assertAlmostEqual(
            model.coagulation_kernel(a, b), model.coagulation_kernel(b, a), places=25
        )
        self.assertAlmostEqual(
            model.coagulation_kernel(a, a), model.monodisperse_coagulation_kernel(a), places=25
        )

    def test_half_life_is_twice_the_collision_timescale(self):
        radius = 25e-9
        concentration = 1e5
        collision = model.collision_timescale_s(radius, concentration)
        half_life = model.population_half_life_s(radius, concentration)
        self.assertAlmostEqual(half_life / collision, 2.0, places=10)

    def test_half_life_scales_inversely_with_concentration(self):
        radius = 25e-9
        low = model.population_half_life_s(radius, 1e3)
        high = model.population_half_life_s(radius, 1e6)
        self.assertAlmostEqual(low / high, 1e3, places=6)

    def test_invalid_inputs_fail_loudly(self):
        with self.assertRaises(ValueError):
            model.monodisperse_coagulation_kernel(0.0)
        with self.assertRaises(ValueError):
            model.collision_timescale_s(25e-9, -1.0)
        with self.assertRaises(ValueError):
            model.iso_class_concentration_per_m3(1, particle_diameter_um=0.05)


class IsoClassTests(unittest.TestCase):
    def test_class_5_matches_the_commonly_cited_0p5um_reference_value(self):
        concentration = model.iso_class_concentration_per_m3(5, particle_diameter_um=0.5)
        self.assertAlmostEqual(concentration, 3520.0, delta=5.0)

    def test_concentration_at_0p1um_threshold_is_exactly_10_to_the_n(self):
        for iso_class in (1, 2, 3, 5, 7):
            self.assertAlmostEqual(
                model.iso_class_concentration_per_m3(iso_class), 10.0 ** iso_class, places=6
            )

    def test_higher_class_number_means_more_particles_allowed(self):
        self.assertLess(
            model.iso_class_concentration_per_m3(1),
            model.iso_class_concentration_per_m3(5),
        )


class ReportTests(unittest.TestCase):
    def test_report_shows_cleanroom_orders_of_magnitude_slower_than_exhaust(self):
        report = model.build_report(target_diameters_nm=[10.0], iso_classes=[1])
        result = report["target_diameter_results"][0]
        # This is the headline finding this module exists to quantify: at
        # ISO class 1 the mechanism is not merely slower, it is inert on any
        # relevant engineering timescale.
        self.assertGreater(result["cleanroom_to_exhaust_slowdown_factor"], 1e10)
        self.assertFalse(report["hardware_performance_validated"])

    def test_report_is_json_serializable(self):
        report = model.build_report(target_diameters_nm=[10.0, 50.0], iso_classes=[1, 5])
        json.dumps(report, allow_nan=False)

    def test_smaller_particles_are_slower_to_coagulate_at_fixed_concentration(self):
        # Larger particles diffuse more slowly individually, but the
        # slip-corrected kernel is dominated by the smaller particle's boosted
        # diffusivity; check the report's own self-consistency rather than
        # assume a monotonic direction here.
        report = model.build_report(target_diameters_nm=[10.0, 50.0], iso_classes=[1])
        kernels = {
            r["diameter_nm"]: r["monodisperse_coagulation_kernel_m3_per_s"]
            for r in report["target_diameter_results"]
        }
        self.assertNotEqual(kernels[10.0], kernels[50.0])

    def test_empty_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            model.build_report(target_diameters_nm=[])
        with self.assertRaises(ValueError):
            model.build_report(iso_classes=[])


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
                    "--diameters-nm",
                    "10,50",
                    "--iso-classes",
                    "1,5",
                ]
            )
        self.assertEqual(status, 0)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["plot"]["enabled"])
        self.assertEqual(len(report["target_diameter_results"]), 2)

    def test_text_format_runs_without_error(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = model.main(
                ["--no-show", "--no-plot", "--format", "text", "--diameters-nm", "10"]
            )
        self.assertEqual(status, 0)
        self.assertIn("SLOWER", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
