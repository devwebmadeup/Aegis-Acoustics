"""Build and numerical-parity tests for the stateless C reference API."""

import ctypes
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from simulation import aegis_phase_calibration as python_reference


ROOT = Path(__file__).resolve().parents[1]


class Point3(ctypes.Structure):
    _fields_ = [("x_m", ctypes.c_double),
                ("y_m", ctypes.c_double),
                ("z_m", ctypes.c_double)]


class ToFCalibration(ctypes.Structure):
    _fields_ = [
        ("sound_speed_m_s", ctypes.c_double),
        ("time_offset_s", ctypes.c_double),
        ("rms_residual_s", ctypes.c_double),
        ("sample_count", ctypes.c_uint32),
        ("fit_time_offset", ctypes.c_uint32),
    ]


class FocusRequest(ctypes.Structure):
    _fields_ = [
        ("emitter_positions_m", ctypes.POINTER(Point3)),
        ("channel_count", ctypes.c_uint32),
        ("target_m", Point3),
        ("sound_speed_m_s", ctypes.c_double),
        ("frequency_hz", ctypes.c_double),
    ]


class FocusOutput(ctypes.Structure):
    _fields_ = [
        ("capacity", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("delays_s", ctypes.POINTER(ctypes.c_double)),
        ("phases_rad", ctypes.POINTER(ctypes.c_double)),
    ]


class CReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        suffix = ".dylib" if platform.system() == "Darwin" else ".so"
        library_path = Path(cls.temporary_directory.name) / f"libaegis{suffix}"
        command = [
            "cc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
            "-fPIC", "-shared", "-I", str(ROOT / "sdk"),
            str(ROOT / "sdk" / "aegis_core.c"), "-lm", "-o", str(library_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        cls.library = ctypes.CDLL(str(library_path))
        cls.library.Aegis_EstimateSoundSpeed.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ToFCalibration),
        ]
        cls.library.Aegis_EstimateSoundSpeed.restype = ctypes.c_int
        cls.library.Aegis_ComputeFocusReference.argtypes = [
            ctypes.POINTER(FocusRequest), ctypes.POINTER(FocusOutput),
        ]
        cls.library.Aegis_ComputeFocusReference.restype = ctypes.c_int
        cls.library.Aegis_ResultString.argtypes = [ctypes.c_int]
        cls.library.Aegis_ResultString.restype = ctypes.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def test_tof_fit_matches_known_speed_and_offset(self):
        expected_speed = 343.25
        expected_offset = 23e-6
        distances_values = (0.04, 0.09, 0.14, 0.19)
        times_values = tuple(expected_offset + value / expected_speed
                             for value in distances_values)
        distances = (ctypes.c_double * 4)(*distances_values)
        times = (ctypes.c_double * 4)(*times_values)
        result = ToFCalibration()

        status = self.library.Aegis_EstimateSoundSpeed(
            distances, times, 4, True, ctypes.byref(result)
        )

        self.assertEqual(status, 0)
        self.assertAlmostEqual(result.sound_speed_m_s, expected_speed, places=10)
        self.assertAlmostEqual(result.time_offset_s, expected_offset, places=15)
        self.assertLess(result.rms_residual_s, 1e-18)
        self.assertEqual(result.sample_count, 4)
        python_result = python_reference.estimate_sound_speed_from_tof(
            distances_values, times_values
        )
        self.assertAlmostEqual(
            result.sound_speed_m_s, python_result.sound_speed_m_s, places=12
        )
        self.assertAlmostEqual(
            result.time_offset_s, python_result.time_offset_s, places=15
        )

    def test_focus_result_matches_python_reference(self):
        coordinates = ((-0.01, 0.0, 0.0), (0.0, 0.0, 0.0), (0.01, 0.0, 0.0))
        target = (0.002, -0.003, 0.12)
        speed = 343.23
        frequency = 40_000.0
        expected = python_reference.calculate_focus_solution(
            coordinates, target, speed, frequency
        )
        emitters = (Point3 * 3)(*(Point3(*point) for point in coordinates))
        delays = (ctypes.c_double * 3)()
        phases = (ctypes.c_double * 3)()
        request = FocusRequest(emitters, 3, Point3(*target), speed, frequency)
        output = FocusOutput(3, 0, delays, phases)

        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )

        self.assertEqual(status, 0)
        self.assertEqual(output.count, 3)
        for actual, reference in zip(delays, expected.delay_s):
            self.assertAlmostEqual(actual, reference, places=15)
        for actual, reference in zip(phases, expected.phase_rad):
            self.assertAlmostEqual(actual, reference, places=12)

    def test_256_channel_focus_matches_python_reference(self):
        coordinates = python_reference.planar_array_coordinates(16, 16, 0.004)
        target = (0.010, -0.005, 0.120)
        speed = 343.23047763
        frequency = 40_000.0
        expected = python_reference.calculate_focus_solution(
            coordinates, target, speed, frequency
        )
        emitters = (Point3 * 256)(*(Point3(*point) for point in coordinates))
        delays = (ctypes.c_double * 256)()
        phases = (ctypes.c_double * 256)()
        request = FocusRequest(emitters, 256, Point3(*target), speed, frequency)
        output = FocusOutput(256, 0, delays, phases)

        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )

        self.assertEqual(status, 0)
        self.assertEqual(output.count, 256)
        self.assertLess(
            max(abs(actual - reference)
                for actual, reference in zip(delays, expected.delay_s)),
            1.0e-15,
        )
        self.assertLess(
            max(abs(actual - reference)
                for actual, reference in zip(phases, expected.phase_rad)),
            1.0e-11,
        )

    def test_buffer_capacity_is_checked_before_writes(self):
        emitters = (Point3 * 3)(Point3(-1, 0, 0), Point3(0, 0, 0), Point3(1, 0, 0))
        request = FocusRequest(emitters, 3, Point3(0, 0, 1), 343.0, 40_000.0)
        delays = (ctypes.c_double * 2)(123.0, 456.0)
        phases = (ctypes.c_double * 2)(789.0, 987.0)
        output = FocusOutput(2, 0, delays, phases)

        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )

        self.assertEqual(status, -4)
        self.assertEqual(output.count, 3)
        self.assertEqual(tuple(delays), (123.0, 456.0))
        self.assertEqual(tuple(phases), (789.0, 987.0))

        query = FocusOutput(0, 99, None, None)
        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(query)
        )
        self.assertEqual(status, -4)
        self.assertEqual(query.count, 3)

    def test_aliasing_and_excessive_phase_cycles_are_rejected(self):
        emitters = (Point3 * 2)(Point3(0, 0, 0), Point3(10, 0, 0))
        shared = (ctypes.c_double * 2)(123.0, 456.0)
        request = FocusRequest(emitters, 2, Point3(0, 0, 1), 1.0, 1.0)
        output = FocusOutput(2, 0, shared, shared)
        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )
        self.assertEqual(status, -1)
        self.assertEqual(tuple(shared), (123.0, 456.0))
        self.assertEqual(output.count, 0)

        delays = (ctypes.c_double * 2)(123.0, 456.0)
        phases = (ctypes.c_double * 2)(123.0, 456.0)
        request.frequency_hz = 1.0e9
        output = FocusOutput(2, 0, delays, phases)
        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )
        self.assertEqual(status, -5)
        self.assertEqual(tuple(delays), (123.0, 456.0))
        self.assertEqual(tuple(phases), (123.0, 456.0))
        self.assertEqual(output.count, 0)

    def test_origin_constrained_tof_fit_matches_python(self):
        distances_values = (0.1, 0.2, 0.3)
        times_values = tuple(value / 350.0 for value in distances_values)
        distances = (ctypes.c_double * 3)(*distances_values)
        times = (ctypes.c_double * 3)(*times_values)
        result = ToFCalibration()
        status = self.library.Aegis_EstimateSoundSpeed(
            distances, times, 3, 0, ctypes.byref(result)
        )
        expected = python_reference.estimate_sound_speed_from_tof(
            distances_values, times_values, fit_time_offset=False
        )
        self.assertEqual(status, 0)
        self.assertAlmostEqual(result.sound_speed_m_s, expected.sound_speed_m_s)
        self.assertEqual(result.time_offset_s, 0.0)
        self.assertEqual(result.fit_time_offset, 0)

    def test_invalid_and_singular_inputs_fail_without_success_output(self):
        distances = (ctypes.c_double * 2)(0.1, 0.1)
        times = (ctypes.c_double * 2)(0.001, 0.002)
        calibration = ToFCalibration()
        status = self.library.Aegis_EstimateSoundSpeed(
            distances, times, 2, True, ctypes.byref(calibration)
        )
        self.assertEqual(status, -3)
        self.assertEqual(calibration.sample_count, 0)

        status = self.library.Aegis_EstimateSoundSpeed(
            distances, times, 2, 2, ctypes.byref(calibration)
        )
        self.assertEqual(status, -1)
        self.assertEqual(calibration.sample_count, 0)

        fast_times = (ctypes.c_double * 2)(1.0e-6, 2.0e-6)
        status = self.library.Aegis_EstimateSoundSpeed(
            (ctypes.c_double * 2)(0.1, 0.2),
            fast_times,
            2,
            1,
            ctypes.byref(calibration),
        )
        self.assertEqual(status, -5)
        self.assertEqual(calibration.sound_speed_m_s, 0.0)
        self.assertEqual(calibration.time_offset_s, 0.0)
        self.assertEqual(calibration.rms_residual_s, 0.0)
        self.assertEqual(calibration.sample_count, 0)

        emitters = (Point3 * 1)(Point3(0, 0, 0))
        delays = (ctypes.c_double * 1)()
        phases = (ctypes.c_double * 1)()
        request = FocusRequest(
            emitters, 1, Point3(0, 0, 1), math.nan, 40_000.0
        )
        output = FocusOutput(1, 99, delays, phases)
        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(request), ctypes.byref(output)
        )
        self.assertEqual(status, -1)
        self.assertEqual(output.count, 0)

        late_invalid_emitters = (Point3 * 2)(
            Point3(0, 0, 0), Point3(math.nan, 0, 0)
        )
        sentinel_delays = (ctypes.c_double * 2)(123.0, 456.0)
        sentinel_phases = (ctypes.c_double * 2)(789.0, 987.0)
        late_request = FocusRequest(
            late_invalid_emitters, 2, Point3(0, 0, 1), 343.0, 40_000.0
        )
        late_output = FocusOutput(
            2, 99, sentinel_delays, sentinel_phases
        )
        status = self.library.Aegis_ComputeFocusReference(
            ctypes.byref(late_request), ctypes.byref(late_output)
        )
        self.assertEqual(status, -1)
        self.assertEqual(late_output.count, 0)
        self.assertEqual(tuple(sentinel_delays), (123.0, 456.0))
        self.assertEqual(tuple(sentinel_phases), (789.0, 987.0))

    def test_ctypes_layout_matches_compiled_c_abi(self):
        source = r'''\
#include <stddef.h>
#include <stdio.h>
#include "aegis_core.h"

int main(void) {
    printf(
        "%zu %zu %zu %zu %zu %zu %zu %zu %zu %zu %zu %zu\n",
        sizeof(AegisResult),
        sizeof(AegisPoint3),
        sizeof(AegisToFCalibration),
        offsetof(AegisToFCalibration, sample_count),
        offsetof(AegisToFCalibration, fit_time_offset),
        sizeof(AegisFocusRequest),
        offsetof(AegisFocusRequest, channel_count),
        offsetof(AegisFocusRequest, target_m),
        offsetof(AegisFocusRequest, sound_speed_m_s),
        sizeof(AegisFocusOutput),
        offsetof(AegisFocusOutput, delays_s),
        offsetof(AegisFocusOutput, phases_rad)
    );
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "abi_probe.c"
            executable_path = Path(directory) / "abi_probe"
            source_path.write_text(source, encoding="utf-8")
            subprocess.run(
                [
                    "cc", "-std=c11", "-Wall", "-Wextra", "-Wpedantic",
                    "-Werror", "-I", str(ROOT / "sdk"), str(source_path),
                    "-o", str(executable_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            actual = tuple(
                int(value)
                for value in subprocess.run(
                    [os.fspath(executable_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.split()
            )

        expected = (
            ctypes.sizeof(ctypes.c_int32),
            ctypes.sizeof(Point3),
            ctypes.sizeof(ToFCalibration),
            ToFCalibration.sample_count.offset,
            ToFCalibration.fit_time_offset.offset,
            ctypes.sizeof(FocusRequest),
            FocusRequest.channel_count.offset,
            FocusRequest.target_m.offset,
            FocusRequest.sound_speed_m_s.offset,
            ctypes.sizeof(FocusOutput),
            FocusOutput.delays_s.offset,
            FocusOutput.phases_rad.offset,
        )
        self.assertEqual(actual, expected)

    def test_result_strings_are_stable(self):
        self.assertEqual(
            self.library.Aegis_ResultString(-4).decode("ascii"),
            "buffer too small",
        )
        self.assertEqual(
            self.library.Aegis_ResultString(-999).decode("ascii"),
            "unknown result",
        )


if __name__ == "__main__":
    unittest.main()
