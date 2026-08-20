"""Tests for the conservative measured relative-phase evidence path."""

from __future__ import annotations

import contextlib
import csv
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from analysis import aegis_phase_measurement_analysis as analysis
from simulation.aegis_phase_calibration import (
    TAU,
    calculate_focus_solution,
    planar_array_coordinates,
)


FREQUENCY_HZ = 40_000.0
SOUND_SPEED_M_S = 343.0
TARGET_M = (0.007, -0.004, 0.120)


def _measurement_run(
    *,
    provenance: str = "experimental",
    global_offset_rad: float = 0.35,
    residual_by_channel: dict[int, float] | None = None,
) -> analysis.PhaseMeasurementRun:
    coordinates = planar_array_coordinates(16, 16, 0.004)
    prediction = calculate_focus_solution(
        coordinates,
        TARGET_M,
        SOUND_SPEED_M_S,
        FREQUENCY_HZ,
    )
    residual_by_channel = residual_by_channel or {}
    measurements = tuple(
        analysis.PhaseMeasurement(
            channel_id=index,
            emitter_m=coordinate,
            measured_drive_phase_rad=(
                predicted_phase
                + global_offset_rad
                + residual_by_channel.get(index, 0.0)
            )
            % TAU,
        )
        for index, (coordinate, predicted_phase) in enumerate(
            zip(coordinates, prediction.phase_rad)
        )
    )
    return analysis.PhaseMeasurementRun(
        provenance=provenance,
        protocol_id="phase-protocol-v1",
        device_id="array-001",
        run_id="run-001",
        instrument_id="phase-meter-001",
        calibration_record_id="cal-2026-001",
        measurement_plane=analysis.MEASUREMENT_PLANE,
        phase_reference_id="reference-clock-001",
        phase_convention=analysis.PHASE_CONVENTION,
        frequency_hz=FREQUENCY_HZ,
        sound_speed_m_s=SOUND_SPEED_M_S,
        target_m=TARGET_M,
        measurements=measurements,
    )


def _csv_row(
    *,
    channel_id: object,
    emitter_m: tuple[float, float, float],
    measured_drive_phase_rad: float,
    provenance: str = "experimental",
    protocol_id: str = "phase-protocol-v1",
    device_id: str = "array-001",
    run_id: str = "run-001",
    instrument_id: str = "phase-meter-001",
    calibration_record_id: str = "cal-2026-001",
    measurement_plane: str = analysis.MEASUREMENT_PLANE,
    phase_reference_id: str = "reference-clock-001",
    phase_convention: str = analysis.PHASE_CONVENTION,
    frequency_hz: float = FREQUENCY_HZ,
    sound_speed_m_s: float = SOUND_SPEED_M_S,
    target_m: tuple[float, float, float] = TARGET_M,
) -> dict[str, object]:
    return {
        "provenance": provenance,
        "protocol_id": protocol_id,
        "device_id": device_id,
        "run_id": run_id,
        "instrument_id": instrument_id,
        "calibration_record_id": calibration_record_id,
        "measurement_plane": measurement_plane,
        "phase_reference_id": phase_reference_id,
        "phase_convention": phase_convention,
        "channel_id": channel_id,
        "emitter_x_m": emitter_m[0],
        "emitter_y_m": emitter_m[1],
        "emitter_z_m": emitter_m[2],
        "frequency_hz": frequency_hz,
        "sound_speed_m_s": sound_speed_m_s,
        "target_x_m": target_m[0],
        "target_y_m": target_m[1],
        "target_z_m": target_m[2],
        "measured_drive_phase_rad": measured_drive_phase_rad,
    }


def _rows_for_run(run: analysis.PhaseMeasurementRun) -> list[dict[str, object]]:
    return [
        _csv_row(
            channel_id=item.channel_id,
            emitter_m=item.emitter_m,
            measured_drive_phase_rad=item.measured_drive_phase_rad,
            provenance=run.provenance,
            protocol_id=run.protocol_id,
            device_id=run.device_id,
            run_id=run.run_id,
            instrument_id=run.instrument_id,
            calibration_record_id=run.calibration_record_id,
            measurement_plane=run.measurement_plane,
            phase_reference_id=run.phase_reference_id,
            phase_convention=run.phase_convention,
            frequency_hz=run.frequency_hz,
            sound_speed_m_s=run.sound_speed_m_s,
            target_m=run.target_m,
        )
        for item in run.measurements
    ]


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: tuple[str, ...] = analysis.REQUIRED_COLUMNS,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class CircularAnalysisTests(unittest.TestCase):
    def test_signed_difference_crosses_wrap_boundary(self):
        self.assertAlmostEqual(
            analysis.signed_circular_difference_rad(0.01, TAU - 0.01),
            0.02,
            places=14,
        )
        self.assertAlmostEqual(
            analysis.signed_circular_difference_rad(TAU - 0.01, 0.01),
            -0.02,
            places=14,
        )

    def test_global_circular_offset_is_removed(self):
        run = _measurement_run(global_offset_rad=TAU - 0.04)
        report = analysis.analyze_measurement_run(
            run,
            p95_threshold_deg=0.01,
            max_threshold_deg=0.01,
            instrument_calibrated=True,
            thresholds_prespecified=True,
        )

        self.assertAlmostEqual(
            report["global_circular_offset"]["rad"], -0.04, places=12
        )
        self.assertLess(report["residual_metrics"]["rad"]["max"], 1e-12)
        self.assertEqual(
            report["global_circular_offset"]["fitted_degrees_of_freedom"], 1
        )
        self.assertEqual(
            report["comparison"]["domain"], "electrical_drive_output"
        )
        self.assertEqual(
            report["comparison"]["phase_convention"],
            "cos_omega_t_plus_phi",
        )
        self.assertFalse(
            report["comparison"]["target_microphone_or_acoustic_arrival_supported"]
        )
        self.assertTrue(report["passed"])
        self.assertTrue(report["single_run_relative_drive_phase_rule_passed"])
        self.assertTrue(report["gate"]["dataset_rule_passed"])
        self.assertFalse(report["experimental_label_authenticated"])
        self.assertFalse(report["device_performance_validated"])

    def test_one_bad_channel_passes_p95_but_fails_maximum_gate(self):
        run = _measurement_run(
            residual_by_channel={137: math.radians(20.0)}
        )
        report = analysis.analyze_measurement_run(
            run,
            p95_threshold_deg=1.0,
            max_threshold_deg=1.0,
            instrument_calibrated=True,
            thresholds_prespecified=True,
        )

        self.assertLess(report["residual_metrics"]["deg"]["p95"], 1.0)
        self.assertGreater(report["residual_metrics"]["deg"]["max"], 10.0)
        self.assertTrue(report["gate"]["checks"]["p95_within_threshold"])
        self.assertFalse(report["gate"]["checks"]["max_within_threshold"])
        self.assertFalse(report["passed"])

    def test_synthetic_is_always_demonstration_only_and_not_device_evidence(self):
        run = _measurement_run(provenance="synthetic")
        report = analysis.analyze_measurement_run(
            run,
            p95_threshold_deg=1.0,
            max_threshold_deg=1.0,
            instrument_calibrated=True,
            thresholds_prespecified=True,
        )

        self.assertTrue(report["demonstration_only"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["experimental_data_supplied"])
        self.assertFalse(report["single_run_relative_drive_phase_rule_passed"])
        self.assertFalse(report["device_relative_phase_gate_passed"])
        self.assertTrue(
            report["device_relative_phase_gate_passed_is_deprecated_alias"]
        )
        self.assertFalse(report["device_performance_validated"])

    def test_supplied_threshold_values_need_separate_prespecification_attestation(self):
        run = _measurement_run()
        report = analysis.analyze_measurement_run(
            run,
            p95_threshold_deg=1.0,
            max_threshold_deg=1.0,
            instrument_calibrated=True,
        )

        self.assertTrue(report["gate"]["threshold_values_supplied"])
        self.assertFalse(
            report["gate"]["thresholds_prespecified_self_attested"]
        )
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("self-attest" in reason for reason in report["gate"]["failure_reasons"])
        )

    def test_wider_thresholds_are_diagnostic_only_under_project_cap(self):
        report = analysis.analyze_measurement_run(
            _measurement_run(),
            p95_threshold_deg=2.0,
            max_threshold_deg=2.0,
            instrument_calibrated=True,
            thresholds_prespecified=True,
        )

        self.assertLess(report["residual_metrics"]["deg"]["max"], 1e-9)
        self.assertFalse(
            report["gate"]["checks"]["thresholds_within_project_caps"]
        )
        self.assertFalse(report["passed"])
        self.assertEqual(
            report["gate"]["temporary_project_threshold_caps_deg"]["p95"],
            1.0,
        )
        self.assertFalse(
            report["gate"]["temporary_project_threshold_caps_deg"]
            ["is_device_validation"]
        )

    def test_vacuous_180_degree_threshold_is_rejected(self):
        with self.assertRaisesRegex(analysis.MeasurementDataError, "vacuous"):
            analysis.analyze_measurement_run(
                _measurement_run(),
                p95_threshold_deg=180.0,
                max_threshold_deg=1.0,
            )

    def test_gate_requires_complete_coverage_and_calibration_attestation(self):
        complete = _measurement_run()
        incomplete = replace(
            complete, measurements=complete.measurements[:-1]
        )
        incomplete_report = analysis.analyze_measurement_run(
            incomplete,
            p95_threshold_deg=1.0,
            max_threshold_deg=1.0,
            instrument_calibrated=True,
            thresholds_prespecified=True,
        )
        self.assertFalse(incomplete_report["coverage"]["complete"])
        self.assertFalse(incomplete_report["passed"])

        uncalibrated_report = analysis.analyze_measurement_run(
            complete,
            p95_threshold_deg=1.0,
            max_threshold_deg=1.0,
            instrument_calibrated=False,
            thresholds_prespecified=True,
        )
        self.assertFalse(uncalibrated_report["passed"])
        self.assertFalse(
            uncalibrated_report["gate"]["instrument_calibrated_self_attested"]
        )

        with self.assertRaisesRegex(
            analysis.MeasurementDataError, "calibration_record_id"
        ):
            analysis.analyze_measurement_run(
                replace(complete, calibration_record_id="")
            )

    def test_malformed_direct_api_values_consistently_raise_data_error(self):
        valid = _measurement_run()
        bad_measurement = replace(
            valid.measurements[0], measured_drive_phase_rad=math.inf
        )
        malformed_runs = {
            "target": replace(valid, target_m=None),
            "frequency": replace(valid, frequency_hz=math.nan),
            "measured_phase": replace(
                valid,
                measurements=(bad_measurement, *valid.measurements[1:]),
            ),
            "reference": replace(valid, phase_reference_id=""),
        }
        for name, malformed in malformed_runs.items():
            with self.subTest(name=name):
                with self.assertRaises(analysis.MeasurementDataError):
                    analysis.analyze_measurement_run(malformed)

    def test_ambiguous_global_offset_is_rejected(self):
        coordinates = ((-0.01, 0.0, 0.0), (0.01, 0.0, 0.0))
        prediction = calculate_focus_solution(
            coordinates, TARGET_M, SOUND_SPEED_M_S, FREQUENCY_HZ
        )
        run = analysis.PhaseMeasurementRun(
            provenance="experimental",
            protocol_id="phase-protocol-v1",
            device_id="array-001",
            run_id="ambiguous-run",
            instrument_id="phase-meter-001",
            calibration_record_id="cal-2026-001",
            measurement_plane=analysis.MEASUREMENT_PLANE,
            phase_reference_id="reference-clock-001",
            phase_convention=analysis.PHASE_CONVENTION,
            frequency_hz=FREQUENCY_HZ,
            sound_speed_m_s=SOUND_SPEED_M_S,
            target_m=TARGET_M,
            measurements=(
                analysis.PhaseMeasurement(0, coordinates[0], prediction.phase_rad[0]),
                analysis.PhaseMeasurement(
                    1, coordinates[1], prediction.phase_rad[1] + math.pi
                ),
            ),
        )
        with self.assertRaisesRegex(
            analysis.MeasurementDataError, "offset is undefined"
        ):
            analysis.analyze_measurement_run(run)


class CsvSchemaTests(unittest.TestCase):
    def test_valid_csv_preserves_single_run_metadata(self):
        rows = [
            _csv_row(channel_id=0, emitter_m=(-0.002, 0.0, 0.0), measured_drive_phase_rad=0.1),
            _csv_row(channel_id=1, emitter_m=(0.002, 0.0, 0.0), measured_drive_phase_rad=0.2),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "run.csv"
            _write_csv(path, rows)
            run = analysis.load_measurement_csv(path)

        self.assertEqual(run.protocol_id, "phase-protocol-v1")
        self.assertEqual(run.instrument_id, "phase-meter-001")
        self.assertEqual(run.calibration_record_id, "cal-2026-001")
        self.assertEqual(run.measurement_plane, analysis.MEASUREMENT_PLANE)
        self.assertEqual(run.phase_convention, analysis.PHASE_CONVENTION)
        self.assertEqual([item.channel_id for item in run.measurements], [0, 1])

    def test_wrong_plane_convention_and_target_arrival_domain_are_rejected(self):
        cases = {
            "wrong_plane": (
                _csv_row(
                    channel_id=0,
                    emitter_m=(0.0, 0.0, 0.0),
                    measured_drive_phase_rad=0.1,
                    measurement_plane="transducer_surface",
                ),
                "measurement_plane must be exactly",
            ),
            "wrong_convention": (
                _csv_row(
                    channel_id=0,
                    emitter_m=(0.0, 0.0, 0.0),
                    measured_drive_phase_rad=0.1,
                    phase_convention="sin_omega_t_plus_phi",
                ),
                "phase_convention must be exactly",
            ),
            "target_arrival": (
                _csv_row(
                    channel_id=0,
                    emitter_m=(0.0, 0.0, 0.0),
                    measured_drive_phase_rad=0.1,
                    measurement_plane="target_microphone_acoustic_arrival",
                ),
                "require a separate analysis",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for name, (row, message) in cases.items():
                with self.subTest(name=name):
                    path = directory / f"{name}.csv"
                    _write_csv(path, [row])
                    with self.assertRaisesRegex(
                        analysis.MeasurementDataError, message
                    ):
                        analysis.load_measurement_csv(path)

    def test_parse_and_sha256_are_bound_to_one_read_snapshot(self):
        rows = [
            _csv_row(
                channel_id=0,
                emitter_m=(-0.002, 0.0, 0.0),
                measured_drive_phase_rad=0.1,
            ),
            _csv_row(
                channel_id=1,
                emitter_m=(0.002, 0.0, 0.0),
                measured_drive_phase_rad=0.2,
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "snapshot.csv"
            _write_csv(path, rows)
            exact_bytes = path.read_bytes()
            with mock.patch.object(
                Path, "read_bytes", autospec=True, return_value=exact_bytes
            ) as read_bytes:
                report = analysis.analyze_measurement_csv(path)

        read_bytes.assert_called_once()
        self.assertEqual(
            report["input"]["sha256"], hashlib.sha256(exact_bytes).hexdigest()
        )
        self.assertEqual(report["input"]["byte_count"], len(exact_bytes))
        self.assertEqual(
            report["input"]["hash_binding"], "sha256_of_exact_bytes_parsed"
        )

    def test_missing_calibration_traceability_and_nonfinite_phase_are_rejected(self):
        valid = _csv_row(
            channel_id=0,
            emitter_m=(0.0, 0.0, 0.0),
            measured_drive_phase_rad=0.1,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            missing_path = directory / "missing-calibration.csv"
            fields = tuple(
                name
                for name in analysis.REQUIRED_COLUMNS
                if name != "calibration_record_id"
            )
            _write_csv(missing_path, [valid], fields)
            with self.assertRaisesRegex(
                analysis.MeasurementDataError, "calibration_record_id"
            ):
                analysis.load_measurement_csv(missing_path)

            nonfinite_path = directory / "nonfinite.csv"
            nonfinite = dict(valid)
            nonfinite["measured_drive_phase_rad"] = "nan"
            _write_csv(nonfinite_path, [nonfinite])
            with self.assertRaisesRegex(
                analysis.MeasurementDataError, "must be finite"
            ):
                analysis.load_measurement_csv(nonfinite_path)

    def test_missing_column_and_mixed_condition_are_rejected(self):
        base_rows = [
            _csv_row(channel_id=0, emitter_m=(-0.002, 0.0, 0.0), measured_drive_phase_rad=0.1),
            _csv_row(
                channel_id=1,
                emitter_m=(0.002, 0.0, 0.0),
                measured_drive_phase_rad=0.2,
                frequency_hz=41_000.0,
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            missing_path = directory / "missing.csv"
            fields = tuple(
                name for name in analysis.REQUIRED_COLUMNS
                if name != "measured_drive_phase_rad"
            )
            _write_csv(missing_path, base_rows, fields)
            with self.assertRaisesRegex(
                analysis.MeasurementDataError, "missing columns"
            ):
                analysis.load_measurement_csv(missing_path)

            mixed_path = directory / "mixed.csv"
            _write_csv(mixed_path, base_rows)
            with self.assertRaisesRegex(
                analysis.MeasurementDataError, "differs within one CSV"
            ):
                analysis.load_measurement_csv(mixed_path)

    def test_channel_id_domain_duplicates_and_duplicate_coordinates_are_rejected(self):
        cases = {
            "out_of_range": (
                [
                    _csv_row(
                        channel_id=256,
                        emitter_m=(0.0, 0.0, 0.0),
                        measured_drive_phase_rad=0.1,
                    )
                ],
                "0 through 255",
            ),
            "duplicate_id": (
                [
                    _csv_row(channel_id=0, emitter_m=(-0.001, 0.0, 0.0), measured_drive_phase_rad=0.1),
                    _csv_row(channel_id=0, emitter_m=(0.001, 0.0, 0.0), measured_drive_phase_rad=0.2),
                ],
                "duplicate channel_id",
            ),
            "duplicate_coordinate": (
                [
                    _csv_row(channel_id=0, emitter_m=(0.0, 0.0, 0.0), measured_drive_phase_rad=0.1),
                    _csv_row(channel_id=1, emitter_m=(0.0, 0.0, 0.0), measured_drive_phase_rad=0.2),
                ],
                "duplicate emitter coordinates",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            for name, (rows, message) in cases.items():
                with self.subTest(name=name):
                    path = directory / f"{name}.csv"
                    _write_csv(path, rows)
                    with self.assertRaisesRegex(
                        analysis.MeasurementDataError, message
                    ):
                        analysis.load_measurement_csv(path)


class CommandLineTests(unittest.TestCase):
    def test_summary_only_omits_channel_array_but_retains_count(self):
        run = _measurement_run(provenance="synthetic")
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "summary.csv"
            _write_csv(input_path, _rows_for_run(run))

            full_report = analysis.analyze_measurement_csv(input_path)
            self.assertEqual(len(full_report["channels"]), 256)
            self.assertNotIn("channel_details_included", full_report)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = analysis.main(
                    (str(input_path), "--summary-only", "--report-only")
                )
            summary = json.loads(stdout.getvalue())

        self.assertEqual(status, analysis.EXIT_OK)
        self.assertNotIn("channels", summary)
        self.assertFalse(summary["channel_details_included"])
        self.assertEqual(summary["channel_details_count"], 256)
        self.assertEqual(summary["coverage"]["observed_unique_channels"], 256)

    def test_synthetic_defaults_to_nonzero_but_report_only_returns_zero(self):
        run = _measurement_run(provenance="synthetic")
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            input_path = directory / "synthetic.csv"
            output_path = directory / "report.json"
            _write_csv(input_path, _rows_for_run(run))

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = analysis.main(
                    (
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--p95-threshold-deg",
                        "1",
                        "--max-threshold-deg",
                        "1",
                        "--confirm-prespecified-thresholds",
                        "--instrument-calibrated",
                    )
                )
            document = json.loads(stdout.getvalue())
            output_document = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(status, analysis.EXIT_GATE_FAILED)
            self.assertFalse(document["passed"])
            self.assertEqual(output_document, document)

            with contextlib.redirect_stdout(io.StringIO()):
                report_only_status = analysis.main(
                    (str(input_path), "--report-only")
                )
            self.assertEqual(report_only_status, analysis.EXIT_OK)

    def test_experimental_cli_requires_prespecification_confirmation(self):
        run = _measurement_run(provenance="experimental")
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "experimental.csv"
            _write_csv(input_path, _rows_for_run(run))
            common_args = (
                str(input_path),
                "--p95-threshold-deg",
                "1",
                "--max-threshold-deg",
                "1",
                "--instrument-calibrated",
            )

            without_confirmation_stdout = io.StringIO()
            with contextlib.redirect_stdout(without_confirmation_stdout):
                without_confirmation = analysis.main(common_args)
            unconfirmed_report = json.loads(without_confirmation_stdout.getvalue())
            self.assertEqual(without_confirmation, analysis.EXIT_GATE_FAILED)
            self.assertFalse(unconfirmed_report["passed"])

            confirmed_stdout = io.StringIO()
            with contextlib.redirect_stdout(confirmed_stdout):
                confirmed = analysis.main(
                    (*common_args, "--confirm-prespecified-thresholds")
                )
            confirmed_report = json.loads(confirmed_stdout.getvalue())
            self.assertEqual(confirmed, analysis.EXIT_OK)
            self.assertTrue(confirmed_report["passed"])

    def test_output_may_not_overwrite_input_csv(self):
        run = _measurement_run(provenance="synthetic")
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "source.csv"
            _write_csv(input_path, _rows_for_run(run))
            original = input_path.read_bytes()

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = analysis.main(
                    (
                        str(input_path),
                        "--output",
                        str(input_path),
                        "--report-only",
                    )
                )
            error = json.loads(stderr.getvalue())
            self.assertEqual(status, analysis.EXIT_INPUT_ERROR)
            self.assertIn("refusing to overwrite", error["error"]["message"])
            self.assertEqual(input_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
