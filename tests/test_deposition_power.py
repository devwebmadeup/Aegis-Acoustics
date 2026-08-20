"""Tests for the prospective deposition power-protocol planner."""

import contextlib
import copy
import io
import json
import math
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analysis import aegis_deposition_power as power


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_CONFIG = REPOSITORY_ROOT / "examples" / "deposition_protocol_config.json"
PROTOCOL_TEMPLATE = REPOSITORY_ROOT / "examples" / "deposition_protocol_template.json"


def quick_plan(protocol_id="TEST-PROTOCOL", **overrides):
    options = {
        "device_id": "DEVICE-1",
        "particle_nm": 100.0,
        "gas": "air",
        "flow_slm": 10.0,
        "exposure_s": 600.0,
        "sampled_area_cm2": 25.0,
        "measurement_method_id": "METHOD-1",
        "exclusion_policy_id": "EXCLUSION-1",
        "stopping_rule_id": "STOP-EXACT-N-1",
        "replacement_policy_id": "REPLACEMENT-NONE-1",
        "mc_search_resamples": power.MINIMUM_MC_RESAMPLES,
        "mc_search_seed": 12345,
        "mc_validation_resamples": power.MINIMUM_MC_RESAMPLES,
        "mc_validation_seed": 67890,
    }
    options.update(overrides)
    return power.plan_power(protocol_id, **options)


class PowerPlanningTests(unittest.TestCase):
    def test_hypothesis_direction_tail_and_joint_recommendation(self):
        document = quick_plan()
        hypotheses = document["power_plan"]["hypotheses"]
        formula = document["power_plan"]["formula"]
        simulation = document["power_plan"]["joint_gate_simulation"]
        result = simulation["result"]
        gate = document["analysis_gate"]

        self.assertAlmostEqual(
            hypotheses["null_boundary_log_ratio"], math.log(0.70)
        )
        self.assertAlmostEqual(
            hypotheses["anticipated_alternative_log_ratio"], math.log(0.55)
        )
        self.assertLess(
            hypotheses["anticipated_alternative_log_ratio"],
            hypotheses["null_boundary_log_ratio"],
        )
        self.assertEqual(hypotheses["two_sided_alpha"], 0.05)
        self.assertEqual(hypotheses["one_sided_upper_tail_alpha"], 0.025)
        self.assertAlmostEqual(formula["per_order_screening_power"], 0.90)
        self.assertGreaterEqual(
            result["wilson_95_percent_lower"],
            simulation["target_joint_power"],
        )
        self.assertEqual(
            gate["minimum_independent_runs"],
            2 * gate["minimum_runs_per_order"],
        )
        self.assertEqual(
            result["total_independent_runs"],
            gate["minimum_independent_runs"],
        )
        self.assertGreaterEqual(
            result["runs_per_order"],
            formula["normal_screening_runs_per_order"],
        )
        self.assertFalse(simulation["validated_against_actual_bootstrap_gate"])
        self.assertFalse(simulation["exact_or_full_analyzer_gate_simulation"])
        self.assertTrue(document["protocol"]["prospective_only"])
        self.assertFalse(document["protocol"]["hardware_performance_validated"])
        self.assertFalse(document["protocol"]["example_only"])
        self.assertTrue(document["protocol"]["execution_eligible"])
        self.assertEqual(
            document["protocol"]["execution_eligibility_rule"],
            "lock_eligible_and_not_example_only",
        )

    def test_seeded_plan_and_fingerprint_are_deterministic(self):
        first = quick_plan()
        second = quick_plan()
        self.assertEqual(first, second)
        self.assertEqual(
            first["protocol_fingerprint"]["canonical_sha256"],
            power.canonical_protocol_sha256(first),
        )
        self.assertEqual(
            first["protocol_fingerprint"]["proves"], "content_identity_only"
        )
        self.assertIn(
            "creation_time_or_pre_registration_chronology",
            first["protocol_fingerprint"]["does_not_prove"],
        )

    def test_versioned_rng_and_quick_plan_have_golden_outputs(self):
        self.assertGreater(power._open_unit_interval_from_uint64(0), 0.0)
        self.assertLess(
            power._open_unit_interval_from_uint64((1 << 64) - 1), 1.0
        )
        normals = power._deterministic_standard_normals(
            12345, 3, stream_domain="golden_test"
        )
        self.assertEqual(
            normals.tolist(),
            [
                [1.608298786582, -0.79813736664],
                [1.506485418749, 0.460171905822],
                [1.151960129103, -0.856133321719],
            ],
        )
        document = quick_plan()
        self.assertEqual(
            document["algorithm"],
            {
                "planner_algorithm_id": power.PLANNER_ALGORITHM_ID,
                "rng_algorithm_id": power.RNG_ALGORITHM_ID,
            },
        )
        self.assertEqual(
            document["protocol_fingerprint"]["canonical_sha256"],
            "50d5c40754871e8371b5d3d3dd7993568c24081b399bf68b47f07f61d05d7b30",
        )
        search = power._deterministic_standard_normals(
            0, 4, stream_domain="sample_size_search"
        )
        shifted_seed = (2 * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        validation = power._deterministic_standard_normals(
            shifted_seed, 4, stream_domain="independent_final_validation"
        )
        self.assertFalse((search[1:] == validation[:-1]).all())

    def test_scope_exact_counts_and_independent_validation_are_bound(self):
        document = quick_plan()
        scope = document["protocol"]["experimental_scope"]
        self.assertEqual(
            set(scope),
            {
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
            },
        )
        simulation = document["power_plan"]["joint_gate_simulation"]
        self.assertNotEqual(
            simulation["search"]["seed"],
            simulation["independent_validation"]["seed"],
        )
        self.assertNotEqual(
            simulation["search"]["stream_domain"],
            simulation["independent_validation"]["stream_domain"],
        )
        self.assertTrue(
            simulation["independent_validation"][
                "wilson_lower_requirement_met"
            ]
        )
        self.assertEqual(
            simulation["result"], simulation["independent_validation"]["result"]
        )
        recommendation = document["power_plan"]["recommended_independent_runs"]
        self.assertTrue(recommendation["acceptance_requires_exact_counts"])
        self.assertTrue(recommendation["unplanned_continuation_is_gate_ineligible"])
        self.assertEqual(document["power_plan"]["power_basis"], "surrogate_power_only")
        self.assertFalse(document["power_plan"]["actual_bootstrap_gate_validated"])

    def test_pilot_sd_is_inflated_and_requires_independent_run_count(self):
        document = quick_plan(
            pilot_log_ratio_sd=0.20,
            pilot_independent_run_count=12,
            conservative_assumed_log_ratio_sd=None,
            pilot_sd_design_multiplier=1.5,
        )
        source = document["power_plan"]["assumptions"]["sd_source"]
        self.assertEqual(source["kind"], "pilot_independent_run_log_ratio_sd")
        self.assertEqual(source["pilot_independent_run_count"], 12)
        self.assertAlmostEqual(source["design_sd"], 0.30)
        self.assertIn("not a formal upper confidence bound", source["warning"])

        with self.assertRaises((TypeError, ValueError)):
            quick_plan(
                pilot_log_ratio_sd=0.20,
                conservative_assumed_log_ratio_sd=None,
            )

        for multiplier in (1.0, 1.249999):
            with self.subTest(multiplier=multiplier), self.assertRaisesRegex(
                ValueError, ">= 1.25"
            ):
                quick_plan(
                    pilot_log_ratio_sd=0.20,
                    pilot_independent_run_count=12,
                    conservative_assumed_log_ratio_sd=None,
                    pilot_sd_design_multiplier=multiplier,
                )

        with self.assertRaisesRegex(ValueError, ">= 12"):
            quick_plan(
                pilot_log_ratio_sd=0.20,
                pilot_independent_run_count=11,
                conservative_assumed_log_ratio_sd=None,
                pilot_sd_design_multiplier=1.25,
            )

    def test_sd_sensitivity_reports_larger_joint_plans(self):
        document = quick_plan()
        sensitivity = document["power_plan"]["sensitivity_scenarios"]
        totals = [
            item["joint_surrogate_recommended_total_independent_runs"]
            for item in sensitivity
        ]
        self.assertEqual(
            [item["design_sd_factor"] for item in sensitivity],
            [1.0, 1.25, 1.5],
        )
        self.assertEqual(totals, sorted(totals))
        self.assertGreater(totals[-1], totals[0])
        self.assertTrue(
            all(
                item["joint_surrogate_wilson_95_percent_lower"] >= 0.80
                for item in sensitivity
            )
        )
        self.assertTrue(
            all(
                item["joint_surrogate_recommended_runs_per_order"]
                >= item["normal_screening_runs_per_order"]
                for item in sensitivity
            )
        )

    def test_invalid_or_diagnostic_only_designs_are_rejected(self):
        invalid_options = (
            {"minimum_reduction_fraction": 0.45},
            {"anticipated_reduction_fraction": 0.30},
            {"target_joint_power": 0.5},
            {"conservative_assumed_log_ratio_sd": 0.0},
            {"analysis_blank_policy": "paired_subtract"},
            {"mc_search_resamples": power.MINIMUM_MC_RESAMPLES - 1},
            {"mc_validation_resamples": power.MAXIMUM_MC_RESAMPLES + 1},
            {
                "analysis_bootstrap_resamples": (
                    power.MAXIMUM_ANALYSIS_BOOTSTRAP_RESAMPLES + 1
                )
            },
            {"minimum_order_balance_ratio": 0.0},
            {"max_order_ratio_fold_difference": 0.99},
            {"mc_validation_seed": 12345},
        )
        for options in invalid_options:
            with self.subTest(options=options), self.assertRaises(
                (TypeError, ValueError)
            ):
                quick_plan(**options)

        with self.assertRaises(ValueError):
            quick_plan(
                pilot_log_ratio_sd=0.2,
                pilot_independent_run_count=10,
            )

    def test_example_only_is_a_strict_boolean_and_blocks_execution(self):
        example = quick_plan(example_only=True)
        self.assertTrue(example["protocol"]["example_only"])
        self.assertTrue(example["protocol"]["lock_eligible"])
        self.assertFalse(example["protocol"]["execution_eligible"])

        for value in (0, 1, "false", None):
            with self.subTest(value=value), self.assertRaisesRegex(
                TypeError, "example_only must be boolean"
            ):
                quick_plan(example_only=value)


class ProtocolVerificationTests(unittest.TestCase):
    def test_repository_config_reproduces_locked_template_exactly(self):
        config = power._load_json_without_duplicates(PROTOCOL_CONFIG)
        locked = power.load_locked_protocol(PROTOCOL_TEMPLATE)
        self.assertEqual(power.plan_from_config(config), locked)
        self.assertEqual(locked["schema_version"], 3)
        self.assertTrue(locked["protocol"]["example_only"])
        self.assertFalse(locked["protocol"]["execution_eligible"])
        self.assertEqual(locked["planning_inputs"]["particle_nm"], 300.0)
        self.assertIn("EXAMPLE-ONLY", locked["protocol"]["protocol_id"])
        self.assertIn("NOT-A-HARDWARE-RECORD", locked["planning_inputs"]["device_id"])
        self.assertEqual(
            locked["protocol_fingerprint"]["canonical_sha256"],
            "0913b1318726ef19dfb966677c037d4ae9278a02a3d2f3089e5aaa7af0620507",
        )

    def test_config_requires_explicit_strict_example_only_marker(self):
        config = power._load_json_without_duplicates(PROTOCOL_CONFIG)
        for value in (0, "true", None):
            altered = copy.deepcopy(config)
            altered["protocol"]["example_only"] = value
            with self.subTest(value=value), self.assertRaisesRegex(
                TypeError, "protocol.example_only must be boolean"
            ):
                power.plan_from_config(altered)

        missing = copy.deepcopy(config)
        del missing["protocol"]["example_only"]
        with self.assertRaisesRegex(ValueError, "contain exactly"):
            power.plan_from_config(missing)

    def test_verifier_returns_copy_and_reproduces_complete_plan(self):
        document = quick_plan()
        verified = power.verify_locked_protocol(document)
        self.assertEqual(verified, document)
        self.assertIsNot(verified, document)
        verified["protocol"]["protocol_id"] = "CHANGED-COPY"
        self.assertEqual(document["protocol"]["protocol_id"], "TEST-PROTOCOL")

    def test_stale_fingerprint_and_rehashed_semantic_forgery_are_rejected(self):
        document = quick_plan()
        stale = copy.deepcopy(document)
        stale["analysis_gate"]["minimum_independent_runs"] += 2
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            power.verify_locked_protocol(stale)

        forged = copy.deepcopy(stale)
        forged["analysis_gate"]["minimum_runs_per_order"] += 1
        forged["power_plan"]["recommended_independent_runs"]["total"] += 2
        forged["power_plan"]["recommended_independent_runs"]["per_order"] += 1
        forged["protocol_fingerprint"]["canonical_sha256"] = (
            power.canonical_protocol_sha256(forged)
        )
        with self.assertRaisesRegex(ValueError, "deterministic result"):
            power.verify_locked_protocol(forged)

    def test_rehashed_changed_mc_claim_is_rejected(self):
        forged = quick_plan()
        forged["power_plan"]["joint_gate_simulation"]["result"][
            "wilson_95_percent_lower"
        ] = 0.999
        forged["protocol_fingerprint"]["canonical_sha256"] = (
            power.canonical_protocol_sha256(forged)
        )
        with self.assertRaisesRegex(ValueError, "deterministic result"):
            power.verify_locked_protocol(forged)

    def test_rehashed_example_marker_change_cannot_reuse_generic_plan(self):
        forged = quick_plan()
        forged["protocol"]["example_only"] = True
        forged["protocol"]["execution_eligible"] = False
        forged["protocol_fingerprint"]["canonical_sha256"] = (
            power.canonical_protocol_sha256(forged)
        )
        with self.assertRaisesRegex(ValueError, "deterministic result"):
            power.verify_locked_protocol(forged)

    def test_rehashed_oversize_bootstrap_lock_is_rejected(self):
        forged = quick_plan()
        forged["planning_inputs"]["analysis_bootstrap_resamples"] = 1_000_001
        forged["analysis_gate"]["bootstrap_resamples"] = 1_000_001
        forged["protocol_fingerprint"]["canonical_sha256"] = (
            power.canonical_protocol_sha256(forged)
        )
        with self.assertRaisesRegex(ValueError, "<= 1000000"):
            power.verify_locked_protocol(forged)

    def test_nondefault_alpha_plan_cannot_be_locked_for_current_analyzer(self):
        document = quick_plan(two_sided_alpha=0.10)
        self.assertFalse(document["protocol"]["lock_eligible"])
        with self.assertRaisesRegex(ValueError, "not compatible"):
            power.verify_locked_protocol(document)

    def test_duplicate_json_keys_are_rejected_before_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                power.load_locked_protocol(path)


class LockAndCommandLineTests(unittest.TestCase):
    def test_verify_cli_is_read_only_and_emits_conservative_receipt(self):
        document = quick_plan()
        with tempfile.TemporaryDirectory() as directory:
            locked_path = Path(directory) / "locked.json"
            power.lock_protocol(document, locked_path)
            before = locked_path.read_bytes()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status_code = power.main(("verify", str(locked_path)))

            self.assertEqual(status_code, 0)
            self.assertEqual(locked_path.read_bytes(), before)
            receipt = json.loads(stdout.getvalue())
            self.assertTrue(receipt["verified"])
            self.assertFalse(receipt["example_only"])
            self.assertTrue(receipt["execution_eligible"])
            self.assertEqual(
                receipt["recommended_total_independent_runs"],
                document["analysis_gate"]["minimum_independent_runs"],
            )
            self.assertGreaterEqual(
                receipt["wilson_95_percent_lower"],
                receipt["target_joint_power"],
            )
            self.assertFalse(receipt["actual_bootstrap_gate_validated"])
            self.assertFalse(receipt["hardware_performance_validated"])
            self.assertFalse(receipt["chronology_proven"])

    def test_plan_cli_rejects_duplicate_config_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "duplicate-config.json"
            config_path.write_text(
                '{"protocol":{},"protocol":{},"planning_inputs":{},'
                '"analysis_gate":{}}',
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status_code = power.main(("plan", str(config_path)))
            self.assertEqual(status_code, 2)
            self.assertIn(
                "duplicate JSON key",
                json.loads(stderr.getvalue())["error"]["message"],
            )

    def test_plan_cli_rejects_oversize_analysis_bootstrap(self):
        config = {
            "protocol": {
                "example_only": False,
                "protocol_id": "CLI-OVERSIZE",
            },
            "planning_inputs": {
                "device_id": "DEVICE-1",
                "particle_nm": 100.0,
                "gas": "air",
                "flow_slm": 10.0,
                "exposure_s": 600.0,
                "sampled_area_cm2": 25.0,
                "measurement_method_id": "METHOD-1",
                "exclusion_policy_id": "EXCLUSION-1",
                "stopping_rule_id": "STOP-EXACT-N-1",
                "replacement_policy_id": "REPLACEMENT-NONE-1",
                "analysis_bootstrap_resamples": 1_000_001,
            },
            "analysis_gate": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = power.main(("plan", str(config_path)))
        self.assertEqual(status, 2)
        self.assertIn("<= 1000000", json.loads(stderr.getvalue())["error"]["message"])

    def test_lock_is_atomic_read_only_and_never_overwrites(self):
        document = quick_plan()
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            output = directory_path / "locked.json"
            power.lock_protocol(document, output)
            before = output.read_bytes()
            self.assertEqual(power.load_locked_protocol(output), document)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode) & stat.S_IWUSR, 0)

            with self.assertRaises(FileExistsError):
                power.lock_protocol(document, output)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(list(directory_path.glob(".locked.json.*.tmp")), [])

    def test_link_failure_removes_temporary_file(self):
        document = quick_plan()
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            output = directory_path / "locked.json"
            with mock.patch.object(
                power.os, "link", side_effect=OSError("link failed")
            ), self.assertRaisesRegex(OSError, "link failed"):
                power.lock_protocol(document, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(directory_path.glob(".locked.json.*.tmp")), [])

    def test_input_and_output_same_path_is_rejected_without_damage(self):
        document = quick_plan()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            original = json.dumps(document, sort_keys=True)
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different files"):
                power.lock_protocol(document, path, input_path=path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_cyclic_symlink_output_is_conservatively_rejected(self):
        document = quick_plan()
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            input_path = directory_path / "plan.json"
            input_path.write_text(json.dumps(document), encoding="utf-8")
            first = directory_path / "cycle-a"
            second = directory_path / "cycle-b"
            try:
                os.symlink(second, first)
                os.symlink(first, second)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(ValueError, "different files"):
                power.lock_protocol(document, first, input_path=input_path)

    def test_plan_and_lock_cli_round_trip_and_nonoverwrite(self):
        config = {
            "protocol": {
                "example_only": False,
                "protocol_id": "CLI-PROTOCOL",
            },
            "planning_inputs": {
                "device_id": "DEVICE-1",
                "particle_nm": 100.0,
                "gas": "air",
                "flow_slm": 10.0,
                "exposure_s": 600.0,
                "sampled_area_cm2": 25.0,
                "measurement_method_id": "METHOD-1",
                "exclusion_policy_id": "EXCLUSION-1",
                "stopping_rule_id": "STOP-EXACT-N-1",
                "replacement_policy_id": "REPLACEMENT-NONE-1",
                "mc_search_resamples": power.MINIMUM_MC_RESAMPLES,
                "mc_search_seed": 77,
                "mc_validation_resamples": power.MINIMUM_MC_RESAMPLES,
                "mc_validation_seed": 78,
            },
            "analysis_gate": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            config_path = directory_path / "config.json"
            plan_path = directory_path / "plan.json"
            lock_path = directory_path / "locked.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status_code = power.main(("plan", str(config_path)))
            self.assertEqual(status_code, 0)
            planned = json.loads(stdout.getvalue())
            power.verify_locked_protocol(planned)
            plan_path.write_text(stdout.getvalue(), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status_code = power.main(
                    ("lock", str(plan_path), "--output", str(lock_path))
                )
            self.assertEqual(status_code, 0)
            receipt = json.loads(stdout.getvalue())
            self.assertTrue(receipt["locked"])
            self.assertFalse(receipt["example_only"])
            self.assertTrue(receipt["execution_eligible"])
            self.assertFalse(receipt["chronology_proven"])
            self.assertEqual(receipt["power_basis"], "surrogate_power_only")
            self.assertFalse(receipt["actual_bootstrap_gate_validated"])
            self.assertFalse(receipt["hardware_performance_validated"])
            before = lock_path.read_bytes()

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status_code = power.main(
                    ("lock", str(plan_path), "--output", str(lock_path))
                )
            self.assertEqual(status_code, 2)
            self.assertEqual(lock_path.read_bytes(), before)
            self.assertEqual(json.loads(stderr.getvalue())["error"]["type"], "FileExistsError")


if __name__ == "__main__":
    unittest.main()
