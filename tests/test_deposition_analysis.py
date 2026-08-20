"""Conservative tests for randomized paired deposition-trial analysis."""

import contextlib
import copy
import csv
import io
import json
import math
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from analysis import aegis_deposition_analysis as deposition


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CSV = REPOSITORY_ROOT / "examples" / "deposition_trial_template.csv"
LOCKED_PROTOCOL_TEMPLATE = (
    REPOSITORY_ROOT / "examples" / "deposition_protocol_template.json"
)

ALL_COLUMNS = (
    list(deposition.REQUIRED_COLUMNS)
    + [
        "sampled_area_cm2",
        "temperature_c",
        "relative_humidity_pct",
    ]
    + list(deposition.BLANK_COLUMNS)
    + list(deposition.TRACEABILITY_COLUMNS)
    + ["notes"]
)


def trial(
    index,
    *,
    block_id=None,
    independent_run_id=None,
    data_provenance="experimental",
    randomized_order=None,
    particle_nm=100.0,
    gas="air",
    flow_slm=10.0,
    exposure_s=600.0,
    sampled_area_cm2=25.0,
    temperature_c=22.0,
    relative_humidity_pct=40.0,
    off_count=100.0,
    on_count=50.0,
    off_blank=None,
    on_blank=None,
    device_id="DEVICE-1",
    trial_day="2026-01-01",
    protocol_id="PROTOCOL-1",
    aerosol_batch_id="BATCH-1",
    measurement_method_id="METHOD-1",
    exclusion_policy_id="EXCLUSION-1",
    stopping_rule_id="STOP-EXACT-N-1",
    replacement_policy_id="REPLACEMENT-NONE-1",
):
    return deposition.PairedTrial(
        block_id=block_id or f"B{index:03d}",
        independent_run_id=independent_run_id or f"R{index:03d}",
        data_provenance=data_provenance,
        randomized_order=randomized_order
        or ("off_then_on" if index % 2 == 0 else "on_then_off"),
        particle_nm=particle_nm,
        gas=gas,
        flow_slm=flow_slm,
        exposure_s=exposure_s,
        sampled_area_cm2=sampled_area_cm2,
        temperature_c=temperature_c,
        relative_humidity_pct=relative_humidity_pct,
        field_off_count=off_count,
        field_on_count=on_count,
        field_off_blank_count=off_blank,
        field_on_blank_count=on_blank,
        device_id=device_id,
        trial_day=trial_day,
        protocol_id=protocol_id,
        aerosol_batch_id=aerosol_batch_id,
        measurement_method_id=measurement_method_id,
        exclusion_policy_id=exclusion_policy_id,
        stopping_rule_id=stopping_rule_id,
        replacement_policy_id=replacement_policy_id,
        notes="test_data",
    )


def base_csv_row(index=1, *, provenance="experimental"):
    item = trial(index, data_provenance=provenance)
    return {
        "block_id": item.block_id,
        "independent_run_id": item.independent_run_id,
        "data_provenance": item.data_provenance,
        "randomized_order": item.randomized_order,
        "particle_nm": str(item.particle_nm),
        "gas": item.gas,
        "flow_slm": str(item.flow_slm),
        "exposure_s": str(item.exposure_s),
        "sampled_area_cm2": str(item.sampled_area_cm2),
        "temperature_c": str(item.temperature_c),
        "relative_humidity_pct": str(item.relative_humidity_pct),
        "field_off_count": str(item.field_off_count),
        "field_on_count": str(item.field_on_count),
        "field_off_blank_count": "",
        "field_on_blank_count": "",
        "device_id": item.device_id,
        "trial_day": item.trial_day,
        "protocol_id": item.protocol_id,
        "aerosol_batch_id": item.aerosol_batch_id,
        "measurement_method_id": item.measurement_method_id,
        "exclusion_policy_id": item.exclusion_policy_id,
        "stopping_rule_id": item.stopping_rule_id,
        "replacement_policy_id": item.replacement_policy_id,
        "notes": item.notes,
    }


def passing_trials(count=8):
    return [trial(index) for index in range(1, count + 1)]


def verified_protocol_for_options(options, *, protocol_id="PROTOCOL-1"):
    gate = {
        "blank_policy": options.get("blank_policy", deposition.BLANK_POLICY_NONE),
        "minimum_reduction_fraction": options["minimum_reduction_fraction"],
        "minimum_independent_runs": options["minimum_independent_runs"],
        "minimum_runs_per_order": options["minimum_runs_per_order"],
        "minimum_order_balance_ratio": options["minimum_order_balance_ratio"],
        "max_order_ratio_fold_difference": options[
            "max_order_ratio_fold_difference"
        ],
        "max_temperature_span_c": options["max_temperature_span_c"],
        "max_relative_humidity_span_pct": options[
            "max_relative_humidity_span_pct"
        ],
        "bootstrap_resamples": options["bootstrap_resamples"],
        "bootstrap_seed": options["seed"],
    }
    return {
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
        },
        "protocol": {
            "protocol_id": protocol_id,
            "example_only": False,
            "execution_eligible": True,
            "prospective_only": True,
            "hardware_performance_validated": False,
        },
        "analysis_gate": gate,
        "protocol_fingerprint": {
            "algorithm": "sha256",
            "canonicalization": "test fixture",
            "canonical_sha256": "0" * 64,
            "proves": "content_identity_only",
            "does_not_prove": ["chronology", "identity", "execution"],
        },
    }


def analysis_options_from_locked(document):
    gate = document["analysis_gate"]
    return {
        "blank_policy": gate["blank_policy"],
        "minimum_reduction_fraction": gate["minimum_reduction_fraction"],
        "minimum_independent_runs": gate["minimum_independent_runs"],
        "minimum_runs_per_order": gate["minimum_runs_per_order"],
        "minimum_order_balance_ratio": gate["minimum_order_balance_ratio"],
        "max_order_ratio_fold_difference": gate[
            "max_order_ratio_fold_difference"
        ],
        "max_temperature_span_c": gate["max_temperature_span_c"],
        "max_relative_humidity_span_pct": gate[
            "max_relative_humidity_span_pct"
        ],
        "bootstrap_resamples": gate["bootstrap_resamples"],
        "seed": gate["bootstrap_seed"],
    }


_CACHED_EXECUTION_PROTOCOL = None


def execution_protocol():
    """Return a non-example deterministic lock for acceptance-path tests."""

    global _CACHED_EXECUTION_PROTOCOL
    if _CACHED_EXECUTION_PROTOCOL is None:
        _CACHED_EXECUTION_PROTOCOL = deposition.deposition_power.plan_power(
            "TEST-EXECUTION-PROTOCOL",
            example_only=False,
            device_id="DEVICE-1",
            particle_nm=300.0,
            gas="air",
            flow_slm=10.0,
            exposure_s=600.0,
            sampled_area_cm2=25.0,
            measurement_method_id="METHOD-1",
            exclusion_policy_id="EXCLUSION-1",
            stopping_rule_id="STOP-EXACT-N-1",
            replacement_policy_id="REPLACEMENT-NONE-1",
            mc_search_resamples=(
                deposition.deposition_power.MINIMUM_MC_RESAMPLES
            ),
            mc_search_seed=54321,
            mc_validation_resamples=(
                deposition.deposition_power.MINIMUM_MC_RESAMPLES
            ),
            mc_validation_seed=98765,
        )
    return copy.deepcopy(_CACHED_EXECUTION_PROTOCOL)


def trials_for_locked_protocol(document):
    scope = document["protocol"]["experimental_scope"]
    protocol_id = document["protocol"]["protocol_id"]
    run_count = document["analysis_gate"]["minimum_independent_runs"]
    return [
        trial(index, protocol_id=protocol_id, **scope)
        for index in range(1, run_count + 1)
    ]


def gate_analysis(trials, **overrides):
    options = {
        "minimum_reduction_fraction": 0.30,
        "minimum_independent_runs": 8,
        "minimum_runs_per_order": 4,
        "minimum_order_balance_ratio": 0.50,
        "max_order_ratio_fold_difference": 1.50,
        "max_temperature_span_c": 1.0,
        "max_relative_humidity_span_pct": 5.0,
        "bootstrap_resamples": 10_000,
        "seed": 123,
        "gate_specification_confirmed": True,
    }
    options.update(overrides)
    if "locked_protocol" in options:
        return deposition.analyze_trials(trials, **options)
    verified = verified_protocol_for_options(options)
    with mock.patch.object(
        deposition.deposition_power,
        "verify_locked_protocol",
        return_value=verified,
    ) as verifier:
        report = deposition.analyze_trials(
            trials,
            locked_protocol={"test_fixture": True},
            **options,
        )
    verifier.assert_called_once_with({"test_fixture": True})
    return report


class TemporaryCsv:
    def __init__(self, rows, fieldnames=ALL_COLUMNS):
        self._directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._directory.name)
        self.path = self.directory / "trial.csv"
        with self.path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)

    def cleanup(self):
        self._directory.cleanup()


class CsvValidationTests(unittest.TestCase):
    def test_template_marks_every_row_synthetic_and_independently_clustered(self):
        trials = deposition.load_paired_trials(EXAMPLE_CSV)
        self.assertEqual(len(trials), 8)
        self.assertEqual({item.data_provenance for item in trials}, {"synthetic"})
        self.assertEqual(len({item.independent_run_id for item in trials}), 8)
        self.assertEqual(
            {item.randomized_order for item in trials},
            {"off_then_on", "on_then_off"},
        )
        self.assertTrue(
            all("never_device_performance" in item.notes for item in trials)
        )

    def test_provenance_and_independent_run_columns_are_required(self):
        for missing in ("data_provenance", "independent_run_id"):
            with self.subTest(missing=missing):
                document = TemporaryCsv(
                    [base_csv_row()],
                    [column for column in ALL_COLUMNS if column != missing],
                )
                try:
                    with self.assertRaisesRegex(ValueError, "missing required column"):
                        deposition.load_paired_trials(document.path)
                finally:
                    document.cleanup()

    def test_provenance_and_independent_run_values_are_validated(self):
        cases = (("data_provenance", "unknown"), ("independent_run_id", ""))
        for column, value in cases:
            with self.subTest(column=column):
                row = base_csv_row()
                row[column] = value
                document = TemporaryCsv([row])
                try:
                    with self.assertRaises(ValueError):
                        deposition.load_paired_trials(document.path)
                finally:
                    document.cleanup()

    def test_zero_negative_missing_and_nonfinite_counts_fail(self):
        for value in ("", "0", "-1", "nan", "inf"):
            with self.subTest(value=value):
                row = base_csv_row()
                row["field_on_count"] = value
                document = TemporaryCsv([row])
                try:
                    with self.assertRaises(ValueError):
                        deposition.load_paired_trials(document.path)
                finally:
                    document.cleanup()

    def test_blank_columns_are_optional_as_a_pair(self):
        no_blank_columns = [
            column for column in ALL_COLUMNS if column not in deposition.BLANK_COLUMNS
        ]
        document = TemporaryCsv([base_csv_row()], no_blank_columns)
        try:
            loaded = deposition.load_paired_trials(document.path)
            self.assertIsNone(loaded[0].field_off_blank_count)
        finally:
            document.cleanup()

        one_blank_column = no_blank_columns + ["field_off_blank_count"]
        document = TemporaryCsv([base_csv_row()], one_blank_column)
        try:
            with self.assertRaisesRegex(ValueError, "supplied together"):
                deposition.load_paired_trials(document.path)
        finally:
            document.cleanup()

    def test_mixed_provenance_and_same_run_with_mixed_order_fail(self):
        with self.assertRaisesRegex(ValueError, "cannot mix synthetic"):
            gate_analysis(
                passing_trials(7) + [trial(8, data_provenance="synthetic")]
            )

        repeated = passing_trials(6)
        repeated.append(
            trial(
                7,
                independent_run_id="R001",
                randomized_order="off_then_on",
            )
        )
        with self.assertRaisesRegex(ValueError, "contains both randomized orders"):
            gate_analysis(repeated)

        inconsistent_scope = passing_trials(8)
        inconsistent_scope.append(
            trial(
                9,
                independent_run_id="R001",
                randomized_order="on_then_off",
                measurement_method_id="METHOD-OTHER",
            )
        )
        with self.assertRaisesRegex(
            ValueError, "traceability or experimental-scope metadata"
        ):
            gate_analysis(inconsistent_scope, locked_protocol=None)

    def test_primary_stratum_fields_cannot_be_pooled(self):
        baseline = passing_trials(8)
        variants = (
            replace(baseline[-1], particle_nm=200.0),
            replace(baseline[-1], gas="n2"),
            replace(baseline[-1], flow_slm=20.0),
            replace(baseline[-1], exposure_s=1200.0),
            replace(baseline[-1], sampled_area_cm2=50.0),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaisesRegex(ValueError, "only one.*stratum"):
                    gate_analysis(
                        baseline[:-1] + [variant], locked_protocol=None
                    )


class ClusterAndStatisticTests(unittest.TestCase):
    def test_experimental_balanced_gate_pass_uses_run_cluster_bootstrap(self):
        report = gate_analysis(passing_trials())
        self.assertEqual(report["prespecified_gate"]["status"], "pass")
        self.assertTrue(report["prespecified_gate"]["passed"])
        self.assertTrue(report["prespecified_gate"]["dataset_rule_passed"])
        self.assertEqual(
            report["prespecified_gate"][
                "passed_is_compatibility_alias_for"
            ],
            "dataset_rule_passed",
        )
        self.assertEqual(report["design"]["unique_independent_run_count"], 8)
        self.assertEqual(
            report["bootstrap"]["method"], "independent_run_cluster_percentile"
        )
        self.assertAlmostEqual(
            report["summary"]["geometric_mean_deposition_reduction_fraction"],
            0.5,
        )
        self.assertTrue(
            report["validation_scope"]["performance_acceptance_gate_passed"]
        )
        self.assertTrue(report["validation_scope"]["analysis_completed"])
        self.assertTrue(
            report["validation_scope"][
                "eligible_for_dataset_rule_evaluation"
            ]
        )
        self.assertEqual(
            report["validation_scope"][
                "hardware_acceptance_eligible_is_compatibility_alias_for"
            ],
            "eligible_for_dataset_rule_evaluation",
        )
        self.assertEqual(
            report["validation_scope"]["power_basis"], "surrogate_power_only"
        )
        self.assertFalse(
            report["validation_scope"]["actual_bootstrap_gate_validated"]
        )
        self.assertFalse(report["validation_scope"]["device_performance_validated"])

    def test_repeated_rows_within_run_do_not_inflate_n_or_weight(self):
        trials = [trial(index) for index in range(1, 7)]
        trials[0] = replace(trials[0], field_on_count=10.0)
        for suffix in range(2, 11):
            trials.append(
                trial(
                    100 + suffix,
                    block_id=f"B001-{suffix}",
                    independent_run_id="R001",
                    randomized_order="on_then_off",
                    on_count=10.0,
                )
            )
        report = gate_analysis(trials)
        expected_ratio = math.exp((math.log(0.1) + 5.0 * math.log(0.5)) / 6.0)
        self.assertEqual(report["design"]["paired_block_count"], 15)
        self.assertEqual(report["design"]["unique_independent_run_count"], 6)
        self.assertAlmostEqual(
            report["summary"]["geometric_mean_field_on_to_off_ratio"],
            expected_ratio,
        )

    def test_bootstrap_seed_and_ci_direction_are_deterministic(self):
        values = (40.0, 45.0, 50.0, 55.0, 60.0, 62.0, 48.0, 58.0)
        trials = [
            trial(index, on_count=value)
            for index, value in enumerate(values, start=1)
        ]
        first = gate_analysis(trials, seed=77)
        second = gate_analysis(trials, seed=77)
        self.assertEqual(first["summary"], second["summary"])
        log_ci = first["summary"]["bootstrap_95_percent_ci_mean_log_ratio"]
        reduction_ci = first["summary"][
            "bootstrap_95_percent_ci_reduction_fraction"
        ]
        self.assertAlmostEqual(
            reduction_ci["lower"], 1.0 - math.exp(log_ci["upper"])
        )
        self.assertAlmostEqual(
            reduction_ci["upper"], 1.0 - math.exp(log_ci["lower"])
        )

    def test_blank_subtraction_is_diagnostic_only_for_experimental_data(self):
        trials = [
            trial(index, off_count=110.0, on_count=60.0, off_blank=10.0, on_blank=10.0)
            for index in range(1, 9)
        ]
        report = gate_analysis(
            trials, blank_policy=deposition.BLANK_POLICY_PAIRED_SUBTRACT
        )
        self.assertAlmostEqual(
            report["summary"]["geometric_mean_field_on_to_off_ratio"], 0.5
        )
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "diagnostic_only_blank_uncertainty_unmodelled",
        )
        self.assertFalse(report["prespecified_gate"]["passed"])
        self.assertFalse(report["validation_scope"]["hardware_acceptance_eligible"])

    def test_nonpositive_blank_corrected_count_fails_without_pseudocount(self):
        trials = [
            trial(index, on_count=10.0, off_blank=0.0, on_blank=10.0)
            for index in range(1, 9)
        ]
        with self.assertRaisesRegex(ValueError, "non-positive field-ON"):
            gate_analysis(
                trials, blank_policy=deposition.BLANK_POLICY_PAIRED_SUBTRACT
            )


class ConservativeGateTests(unittest.TestCase):
    def test_synthetic_data_can_never_pass_performance(self):
        report = gate_analysis(
            [trial(index, data_provenance="synthetic") for index in range(1, 9)]
        )
        self.assertEqual(report["prespecified_gate"]["status"], "demonstration_only")
        self.assertFalse(report["prespecified_gate"]["passed"])
        self.assertFalse(report["prespecified_gate"]["dataset_rule_passed"])
        self.assertTrue(report["validation_scope"]["demonstration_only"])
        self.assertTrue(report["validation_scope"]["analysis_completed"])
        self.assertFalse(
            report["validation_scope"][
                "eligible_for_dataset_rule_evaluation"
            ]
        )
        self.assertFalse(
            report["validation_scope"]["performance_acceptance_gate_passed"]
        )

    def test_thresholds_need_chronology_attestation_and_machine_checked_plan(self):
        report = gate_analysis(
            passing_trials(), gate_specification_confirmed=False
        )
        gate = report["prespecified_gate"]
        self.assertEqual(gate["status"], "indeterminate_not_prespecified")
        self.assertEqual(gate["threshold_source"], "not_confirmed_prespecified")
        self.assertTrue(gate["power_analysis_calculations_machine_verified"])
        self.assertFalse(gate["power_analysis_inputs_validated_by_this_tool"])
        self.assertFalse(gate["power_analysis_input_values_authenticated"])

        confirmed = gate_analysis(passing_trials())["prespecified_gate"]
        self.assertEqual(
            confirmed["threshold_source"],
            "locked_protocol_plus_chronology_self_attestation",
        )
        self.assertEqual(
            confirmed["minimum_run_count_source"],
            "machine_verified_locked_power_protocol",
        )

        no_plan = gate_analysis(
            passing_trials(), locked_protocol=None
        )["prespecified_gate"]
        self.assertEqual(
            no_plan["status"],
            "indeterminate_no_machine_verified_locked_protocol",
        )
        self.assertIn(
            "machine_verified_locked_protocol_was_not_supplied",
            no_plan["failure_reasons"],
        )

    def test_gate_requires_at_least_10000_bootstrap_resamples(self):
        with self.assertRaisesRegex(ValueError, ">= 10000"):
            gate_analysis(passing_trials(), bootstrap_resamples=9_999)

    def test_bootstrap_resample_resource_cap_is_enforced_by_api(self):
        with self.assertRaisesRegex(ValueError, "<= 1000000"):
            gate_analysis(passing_trials(), bootstrap_resamples=1_000_001)

    def test_unique_run_count_not_row_count_controls_gate(self):
        trials = []
        for index in range(1, 5):
            trials.append(trial(index))
            trials.append(
                trial(
                    100 + index,
                    block_id=f"B{index:03d}-repeat",
                    independent_run_id=f"R{index:03d}",
                    randomized_order=(
                        "off_then_on" if index % 2 == 0 else "on_then_off"
                    ),
                )
            )
        report = gate_analysis(trials)
        self.assertEqual(report["design"]["paired_block_count"], 8)
        self.assertEqual(report["design"]["unique_independent_run_count"], 4)
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "fail_locked_sample_size_or_allocation",
        )
        self.assertIn(
            "insufficient_unique_independent_runs",
            report["prespecified_gate"]["failure_reasons"],
        )

    def test_both_order_representation_and_reasonable_balance_are_required(self):
        five_to_one = [
            trial(
                index,
                randomized_order="off_then_on" if index <= 5 else "on_then_off",
            )
            for index in range(1, 7)
        ]
        report = gate_analysis(
            five_to_one,
            minimum_independent_runs=6,
            minimum_runs_per_order=2,
        )
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "fail_locked_sample_size_or_allocation",
        )
        self.assertFalse(report["design"]["exact_locked_order_counts_met"])

        four_to_two = [
            trial(
                index,
                randomized_order="off_then_on" if index <= 4 else "on_then_off",
            )
            for index in range(1, 7)
        ]
        report = gate_analysis(
            four_to_two,
            minimum_independent_runs=6,
            minimum_runs_per_order=2,
            minimum_order_balance_ratio=0.75,
        )
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "fail_locked_sample_size_or_allocation",
        )
        self.assertFalse(report["design"]["order_balance_met"])

    def test_unplanned_continuation_is_rejected_even_when_balanced(self):
        report = gate_analysis(passing_trials(10))
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "fail_locked_sample_size_or_allocation",
        )
        self.assertFalse(
            report["design"]["exact_locked_sample_size_and_allocation_met"]
        )
        self.assertIn(
            "observed_independent_run_counts_do_not_equal_locked_plan",
            report["prespecified_gate"]["failure_reasons"],
        )

    def test_order_specific_effects_and_consistency_are_in_gate(self):
        trials = [
            trial(
                index,
                randomized_order="off_then_on" if index <= 3 else "on_then_off",
                on_count=40.0 if index <= 3 else 65.0,
            )
            for index in range(1, 7)
        ]
        report = gate_analysis(
            trials,
            minimum_independent_runs=6,
            minimum_runs_per_order=3,
        )
        diagnostics = report["randomized_order_diagnostics"]
        self.assertTrue(diagnostics["order_specific_effect_requirement_met"])
        self.assertGreater(diagnostics["observed_ratio_fold_difference"], 1.5)
        self.assertFalse(diagnostics["order_consistency_requirement_met"])
        self.assertEqual(
            report["prespecified_gate"]["status"], "fail_order_inconsistency"
        )

    def test_exact_mc_boundary_is_indeterminate(self):
        trials = [trial(index, on_count=70.0) for index in range(1, 9)]
        report = gate_analysis(trials, minimum_reduction_fraction=0.30)
        self.assertTrue(
            report["prespecified_gate"]["monte_carlo_boundary_indeterminate"]
        )
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "indeterminate_monte_carlo_boundary",
        )

    def test_environment_span_and_measurement_context_block_acceptance(self):
        varied = passing_trials()
        varied[-1] = replace(varied[-1], temperature_c=24.0)
        report = gate_analysis(varied, max_temperature_span_c=1.0)
        self.assertEqual(
            report["prespecified_gate"]["status"], "fail_environment_tolerance"
        )

        missing = passing_trials()
        missing[-1] = replace(missing[-1], relative_humidity_pct=None)
        report = gate_analysis(missing)
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "insufficient_measurement_context",
        )

    def test_traceability_and_single_device_protocol_are_required(self):
        missing = passing_trials()
        missing[-1] = replace(missing[-1], aerosol_batch_id=None)
        report = gate_analysis(missing)
        self.assertEqual(
            report["prespecified_gate"]["status"],
            "insufficient_traceability_metadata",
        )

        pooled = passing_trials()
        pooled[-1] = replace(pooled[-1], device_id="DEVICE-2")
        with self.assertRaisesRegex(ValueError, "experimental scope.*device_id"):
            gate_analysis(pooled)

        missing_scope_rule = passing_trials()
        missing_scope_rule[-1] = replace(
            missing_scope_rule[-1], stopping_rule_id=None
        )
        report = gate_analysis(missing_scope_rule, locked_protocol=None)
        self.assertIn(
            "required_traceability_or_experimental_scope_metadata_missing",
            report["prespecified_gate"]["failure_reasons"],
        )

    def test_day_and_batch_diversity_are_reported_without_an_effect_model(self):
        trials = passing_trials()
        trials[-1] = replace(
            trials[-1], trial_day="2026-01-02", aerosol_batch_id="BATCH-2"
        )
        report = gate_analysis(trials)
        self.assertEqual(report["prespecified_gate"]["status"], "pass")
        self.assertEqual(report["traceability"]["unique_trial_days"], [
            "2026-01-01",
            "2026-01-02",
        ])
        self.assertEqual(len(report["traceability"]["unique_aerosol_batch_ids"]), 2)
        self.assertTrue(any("day or batch effects" in text for text in report["caveats"]))


class LockedProtocolIntegrationTests(unittest.TestCase):
    def test_legacy_power_self_attestation_has_no_api_or_cli_path(self):
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            deposition.analyze_trials(
                passing_trials(),
                power_analysis_confirmed=True,
            )

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            deposition.build_argument_parser().parse_args(
                (str(EXAMPLE_CSV), "--confirm-power-analysis")
            )
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_shipped_example_template_verifies_but_analysis_rejects_it(self):
        locked = deposition.deposition_power.load_locked_protocol(
            LOCKED_PROTOCOL_TEMPLATE
        )
        options = analysis_options_from_locked(locked)
        self.assertTrue(locked["protocol"]["example_only"])
        self.assertFalse(locked["protocol"]["execution_eligible"])
        self.assertEqual(locked["planning_inputs"]["particle_nm"], 300.0)

        with self.assertRaisesRegex(
            ValueError, "example-only.*cannot be used"
        ):
            deposition.analyze_trials(
                trials_for_locked_protocol(locked),
                gate_specification_confirmed=True,
                locked_protocol=locked,
                **options,
            )

    def test_shipped_example_template_is_rejected_by_cli_binding(self):
        locked = deposition.deposition_power.load_locked_protocol(
            LOCKED_PROTOCOL_TEMPLATE
        )
        gate = locked["analysis_gate"]
        scope = locked["protocol"]["experimental_scope"]
        rows = []
        for index in range(1, gate["minimum_independent_runs"] + 1):
            row = base_csv_row(index)
            row.update(
                {
                    "protocol_id": locked["protocol"]["protocol_id"],
                    "device_id": scope["device_id"],
                    "particle_nm": str(scope["particle_nm"]),
                    "gas": scope["gas"],
                    "flow_slm": str(scope["flow_slm"]),
                    "exposure_s": str(scope["exposure_s"]),
                    "sampled_area_cm2": str(scope["sampled_area_cm2"]),
                    "measurement_method_id": scope["measurement_method_id"],
                    "exclusion_policy_id": scope["exclusion_policy_id"],
                    "stopping_rule_id": scope["stopping_rule_id"],
                    "replacement_policy_id": scope["replacement_policy_id"],
                }
            )
            rows.append(row)
        document = TemporaryCsv(rows)
        stderr = io.StringIO()
        arguments = (
            str(document.path),
            "--locked-protocol-json",
            str(LOCKED_PROTOCOL_TEMPLATE),
            "--confirm-prespecified-gate",
            "--blank-policy",
            gate["blank_policy"],
            "--minimum-reduction",
            str(gate["minimum_reduction_fraction"]),
            "--minimum-independent-runs",
            str(gate["minimum_independent_runs"]),
            "--minimum-runs-per-order",
            str(gate["minimum_runs_per_order"]),
            "--minimum-order-balance-ratio",
            str(gate["minimum_order_balance_ratio"]),
            "--max-order-ratio-fold-difference",
            str(gate["max_order_ratio_fold_difference"]),
            "--max-temperature-span-c",
            str(gate["max_temperature_span_c"]),
            "--max-relative-humidity-span-pct",
            str(gate["max_relative_humidity_span_pct"]),
            "--bootstrap-resamples",
            str(gate["bootstrap_resamples"]),
            "--seed",
            str(gate["bootstrap_seed"]),
        )
        try:
            with contextlib.redirect_stderr(stderr):
                status = deposition.main(arguments)
        finally:
            document.cleanup()

        self.assertEqual(status, deposition.EXIT_INPUT_ERROR)
        self.assertIn(
            "example-only",
            json.loads(stderr.getvalue())["error"]["message"],
        )

    def test_non_example_locked_protocol_still_can_pass(self):
        locked = execution_protocol()
        self.assertFalse(locked["protocol"]["example_only"])
        self.assertTrue(locked["protocol"]["execution_eligible"])
        report = deposition.analyze_trials(
            trials_for_locked_protocol(locked),
            gate_specification_confirmed=True,
            locked_protocol=locked,
            **analysis_options_from_locked(locked),
        )
        self.assertTrue(report["prespecified_gate"]["passed"])
        self.assertFalse(
            report["locked_protocol_verification"]["example_only"]
        )
        self.assertTrue(
            report["locked_protocol_verification"]["execution_eligible"]
        )

    def test_tampered_lock_is_rejected_by_python_api(self):
        locked = deposition.deposition_power.load_locked_protocol(
            LOCKED_PROTOCOL_TEMPLATE
        )
        tampered = copy.deepcopy(locked)
        tampered["analysis_gate"]["minimum_reduction_fraction"] += 0.01
        options = analysis_options_from_locked(tampered)
        protocol_id = tampered["protocol"]["protocol_id"]
        trials = [
            trial(index, protocol_id=protocol_id)
            for index in range(1, options["minimum_independent_runs"] + 1)
        ]

        with self.assertRaises(ValueError):
            deposition.analyze_trials(
                trials,
                gate_specification_confirmed=True,
                locked_protocol=tampered,
                **options,
            )

    def test_valid_lock_rejects_option_and_csv_protocol_mismatches(self):
        locked = execution_protocol()
        options = analysis_options_from_locked(locked)
        matching_trials = trials_for_locked_protocol(locked)

        mismatched_options = dict(options)
        mismatched_options["max_order_ratio_fold_difference"] += 0.01
        with self.assertRaisesRegex(ValueError, "max_order_ratio_fold_difference"):
            deposition.analyze_trials(
                matching_trials,
                gate_specification_confirmed=True,
                locked_protocol=locked,
                **mismatched_options,
            )

        wrong_protocol_trials = [
            replace(item, protocol_id="WRONG-PROTOCOL")
            for item in matching_trials
        ]
        with self.assertRaisesRegex(ValueError, "CSV protocol_id"):
            deposition.analyze_trials(
                wrong_protocol_trials,
                gate_specification_confirmed=True,
                locked_protocol=locked,
                **options,
            )

    def test_lock_rejects_every_experimental_scope_mismatch(self):
        options = {
            "minimum_reduction_fraction": 0.30,
            "minimum_independent_runs": 8,
            "minimum_runs_per_order": 4,
            "minimum_order_balance_ratio": 0.50,
            "max_order_ratio_fold_difference": 1.50,
            "max_temperature_span_c": 1.0,
            "max_relative_humidity_span_pct": 5.0,
            "bootstrap_resamples": 10_000,
            "seed": 123,
        }
        verified = verified_protocol_for_options(options)
        replacements = {
            "device_id": "DEVICE-OTHER",
            "particle_nm": 999.0,
            "gas": "n2",
            "flow_slm": 99.0,
            "exposure_s": 999.0,
            "sampled_area_cm2": 99.0,
            "measurement_method_id": "METHOD-OTHER",
            "exclusion_policy_id": "EXCLUSION-OTHER",
            "stopping_rule_id": "STOP-OTHER",
            "replacement_policy_id": "REPLACEMENT-OTHER",
        }
        for field, value in replacements.items():
            with self.subTest(field=field), mock.patch.object(
                deposition.deposition_power,
                "verify_locked_protocol",
                return_value=verified,
            ), self.assertRaisesRegex(ValueError, field):
                deposition.analyze_trials(
                    [replace(item, **{field: value}) for item in passing_trials()],
                    gate_specification_confirmed=True,
                    locked_protocol={"test_fixture": True},
                    **options,
                )

    def test_csv_hash_covers_the_same_snapshot_that_was_parsed(self):
        document = TemporaryCsv(
            [base_csv_row(index, provenance="synthetic") for index in range(1, 9)]
        )
        original_bytes = document.path.read_bytes()
        original_loader = deposition.load_paired_trials

        def mutate_after_snapshot(path, *, _snapshot_bytes=None):
            loaded = original_loader(path, _snapshot_bytes=_snapshot_bytes)
            Path(path).write_text("changed after snapshot\n", encoding="utf-8")
            return loaded

        try:
            with mock.patch.object(
                deposition,
                "load_paired_trials",
                side_effect=mutate_after_snapshot,
            ):
                report = deposition.analyze_csv(document.path)
        finally:
            document.cleanup()

        import hashlib

        self.assertEqual(
            report["input"]["sha256"],
            hashlib.sha256(original_bytes).hexdigest(),
        )
        self.assertEqual(
            report["input"]["sha256_covers"],
            "exact_bytes_parsed_by_this_analysis",
        )


class CommandLineTests(unittest.TestCase):
    def test_synthetic_cli_fails_by_default_and_report_only_returns_zero(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = deposition.main((str(EXAMPLE_CSV),))
        report = json.loads(stdout.getvalue())
        self.assertEqual(status, deposition.EXIT_GATE_FAILED)
        self.assertEqual(report["prespecified_gate"]["status"], "demonstration_only")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = deposition.main((str(EXAMPLE_CSV), "--report-only"))
        self.assertEqual(status, deposition.EXIT_OK)
        self.assertFalse(json.loads(stdout.getvalue())["prespecified_gate"]["passed"])

    def test_cli_rejects_bootstrap_resamples_over_resource_cap(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = deposition.main(
                (
                    str(EXAMPLE_CSV),
                    "--bootstrap-resamples",
                    "1000001",
                    "--report-only",
                )
            )
        self.assertEqual(status, deposition.EXIT_INPUT_ERROR)
        self.assertIn("<= 1000000", json.loads(stderr.getvalue())["error"]["message"])

    def test_experimental_confirmed_gate_passes_cli(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        stdout = io.StringIO()
        options = {
            "minimum_reduction_fraction": 0.30,
            "minimum_independent_runs": 8,
            "minimum_runs_per_order": 4,
            "minimum_order_balance_ratio": 0.50,
            "max_order_ratio_fold_difference": 1.50,
            "max_temperature_span_c": 1.0,
            "max_relative_humidity_span_pct": 5.0,
            "bootstrap_resamples": 10_000,
            "seed": deposition.DEFAULT_BOOTSTRAP_SEED,
        }
        verified = verified_protocol_for_options(options)
        try:
            with mock.patch.object(
                deposition.deposition_power,
                "load_locked_protocol",
                return_value={"test_fixture": True},
            ), mock.patch.object(
                deposition.deposition_power,
                "verify_locked_protocol",
                return_value=verified,
            ), contextlib.redirect_stdout(stdout):
                status = deposition.main(
                    (
                        str(document.path),
                        "--confirm-prespecified-gate",
                        "--locked-protocol-json",
                        str(document.directory / "locked.json"),
                        "--minimum-independent-runs",
                        "8",
                        "--minimum-runs-per-order",
                        "4",
                    )
                )
        finally:
            document.cleanup()
        report = json.loads(stdout.getvalue())
        self.assertEqual(status, deposition.EXIT_OK)
        self.assertTrue(report["prespecified_gate"]["passed"])

    def test_unconfirmed_experimental_gate_is_nonzero_by_default(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                status = deposition.main((str(document.path),))
        finally:
            document.cleanup()
        self.assertEqual(status, deposition.EXIT_GATE_FAILED)
        self.assertEqual(
            json.loads(stdout.getvalue())["prespecified_gate"]["status"],
            "indeterminate_not_prespecified",
        )

    def test_input_and_output_same_path_is_rejected_without_damage(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        before = document.path.read_bytes()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                status = deposition.main(
                    (
                        str(document.path),
                        "--output-json",
                        str(document.path),
                        "--report-only",
                    )
                )
            self.assertEqual(document.path.read_bytes(), before)
        finally:
            document.cleanup()
        self.assertEqual(status, deposition.EXIT_INPUT_ERROR)
        self.assertIn("different files", json.loads(stderr.getvalue())["error"]["message"])

    def test_atomic_output_replaces_symlink_without_touching_its_target(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            target = directory_path / "unrelated.txt"
            target.write_text("unrelated\n", encoding="utf-8")
            output = directory_path / "report.json"
            try:
                os.symlink(target, output)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlinks unavailable: {error}")

            deposition._atomic_write_text(output, "report\n")

            self.assertEqual(target.read_text(encoding="utf-8"), "unrelated\n")
            self.assertFalse(output.is_symlink())
            self.assertEqual(output.read_text(encoding="utf-8"), "report\n")

    def test_symlink_and_hardlink_outputs_to_input_are_rejected(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        before = document.path.read_bytes()
        try:
            for link_kind in ("symlink", "hardlink"):
                output = document.directory / f"{link_kind}.json"
                try:
                    if link_kind == "symlink":
                        os.symlink(document.path, output)
                    else:
                        os.link(document.path, output)
                except (OSError, NotImplementedError) as error:
                    self.skipTest(f"{link_kind} unavailable: {error}")
                stderr = io.StringIO()
                with self.subTest(link_kind=link_kind), contextlib.redirect_stderr(
                    stderr
                ):
                    status = deposition.main(
                        (
                            str(document.path),
                            "--output-json",
                            str(output),
                            "--report-only",
                        )
                    )
                self.assertEqual(status, deposition.EXIT_INPUT_ERROR)
                self.assertIn(
                    "different files",
                    json.loads(stderr.getvalue())["error"]["message"],
                )
                self.assertEqual(document.path.read_bytes(), before)
        finally:
            document.cleanup()

    def test_cyclic_symlink_output_fails_closed_as_json_input_error(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        first = document.directory / "cycle-a"
        second = document.directory / "cycle-b"
        try:
            try:
                os.symlink(second, first)
                os.symlink(first, second)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symlinks unavailable: {error}")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = deposition.main(
                    (
                        str(document.path),
                        "--output-json",
                        str(first),
                        "--report-only",
                    )
                )
            self.assertEqual(status, deposition.EXIT_INPUT_ERROR)
            self.assertIn(
                "different files",
                json.loads(stderr.getvalue())["error"]["message"],
            )
        finally:
            document.cleanup()

    def test_output_write_is_atomic_and_matches_stdout(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        output_path = document.directory / "report.json"
        stdout = io.StringIO()
        options = {
            "minimum_reduction_fraction": 0.30,
            "minimum_independent_runs": 8,
            "minimum_runs_per_order": 4,
            "minimum_order_balance_ratio": 0.50,
            "max_order_ratio_fold_difference": 1.50,
            "max_temperature_span_c": 1.0,
            "max_relative_humidity_span_pct": 5.0,
            "bootstrap_resamples": 10_000,
            "seed": deposition.DEFAULT_BOOTSTRAP_SEED,
        }
        verified = verified_protocol_for_options(options)
        try:
            with mock.patch.object(
                deposition.deposition_power,
                "load_locked_protocol",
                return_value={"test_fixture": True},
            ), mock.patch.object(
                deposition.deposition_power,
                "verify_locked_protocol",
                return_value=verified,
            ), contextlib.redirect_stdout(stdout):
                status = deposition.main(
                    (
                        str(document.path),
                        "--confirm-prespecified-gate",
                        "--locked-protocol-json",
                        str(document.directory / "locked.json"),
                        "--minimum-independent-runs",
                        "8",
                        "--minimum-runs-per-order",
                        "4",
                        "--output-json",
                        str(output_path),
                    )
                )
            temporary_files = list(document.directory.glob(".report.json.*.tmp"))
            self.assertEqual(json.loads(stdout.getvalue()), json.loads(output_path.read_text()))
            self.assertEqual(temporary_files, [])
        finally:
            document.cleanup()
        self.assertEqual(status, deposition.EXIT_OK)

    def test_atomic_replace_failure_preserves_existing_output(self):
        document = TemporaryCsv([base_csv_row(index) for index in range(1, 9)])
        output_path = document.directory / "report.json"
        output_path.write_text("existing\n", encoding="utf-8")
        stderr = io.StringIO()
        options = {
            "minimum_reduction_fraction": 0.30,
            "minimum_independent_runs": 8,
            "minimum_runs_per_order": 4,
            "minimum_order_balance_ratio": 0.50,
            "max_order_ratio_fold_difference": 1.50,
            "max_temperature_span_c": 1.0,
            "max_relative_humidity_span_pct": 5.0,
            "bootstrap_resamples": 10_000,
            "seed": deposition.DEFAULT_BOOTSTRAP_SEED,
        }
        verified = verified_protocol_for_options(options)
        try:
            with mock.patch.object(
                deposition.os, "replace", side_effect=OSError("replace failed")
            ), mock.patch.object(
                deposition.deposition_power,
                "load_locked_protocol",
                return_value={"test_fixture": True},
            ), mock.patch.object(
                deposition.deposition_power,
                "verify_locked_protocol",
                return_value=verified,
            ), contextlib.redirect_stderr(stderr):
                status = deposition.main(
                    (
                        str(document.path),
                        "--confirm-prespecified-gate",
                        "--locked-protocol-json",
                        str(document.directory / "locked.json"),
                        "--minimum-independent-runs",
                        "8",
                        "--minimum-runs-per-order",
                        "4",
                        "--output-json",
                        str(output_path),
                    )
                )
            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing\n")
            self.assertEqual(list(document.directory.glob(".report.json.*.tmp")), [])
        finally:
            document.cleanup()
        self.assertEqual(status, deposition.EXIT_INPUT_ERROR)


if __name__ == "__main__":
    unittest.main()
