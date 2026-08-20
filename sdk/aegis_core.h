/**
 * @file aegis_core.h
 * @brief Stateless reference API for Aegis ToF and phase calculations.
 * @version 0.2.0
 * @copyright 2026 Aegis-Acoustics Project. MIT License.
 *
 * This API implements deterministic host-side geometry only. It does not
 * acquire sensors, drive transducers, validate an acoustic focus, or provide
 * a hardware safety state machine. All coordinates and times use SI units.
 * The caller owns every input and output buffer; the implementation performs
 * no dynamic allocation.
 */

#ifndef AEGIS_CORE_H
#define AEGIS_CORE_H

#include <float.h>
#include <stdint.h>

#if defined(__cplusplus)
static_assert(sizeof(double) == 8 && DBL_MANT_DIG == 53,
              "Aegis reference API requires IEEE-754 binary64 double");
#else
_Static_assert(sizeof(double) == 8 && DBL_MANT_DIG == 53,
               "Aegis reference API requires IEEE-754 binary64 double");
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t AegisResult;

enum {
    AEGIS_SUCCESS = 0,
    AEGIS_ERR_INVALID_PARAMS = -1,
    AEGIS_ERR_INSUFFICIENT_SAMPLES = -2,
    AEGIS_ERR_SINGULAR_CALIBRATION = -3,
    AEGIS_ERR_BUFFER_TOO_SMALL = -4,
    AEGIS_ERR_NUMERIC = -5
};

/* Bound loss of fractional-cycle precision in binary64 phase reduction. */
#define AEGIS_MAX_PHASE_CYCLES 1000000000.0
#define AEGIS_MAX_FREQUENCY_HZ 1000000000.0
#define AEGIS_MIN_SOUND_SPEED_M_S 1.0
#define AEGIS_MAX_SOUND_SPEED_M_S 10000.0
#define AEGIS_MAX_CALIBRATION_DISTANCE_M 1000.0
#define AEGIS_MAX_CALIBRATION_TIME_S 10.0
#define AEGIS_ABI_VERSION 0x00020000U

typedef struct {
    double x_m;
    double y_m;
    double z_m;
} AegisPoint3;

typedef struct {
    double sound_speed_m_s;
    double time_offset_s;
    double rms_residual_s;
    uint32_t sample_count;
    uint32_t fit_time_offset;
} AegisToFCalibration;

typedef struct {
    const AegisPoint3 *emitter_positions_m;
    uint32_t channel_count;
    AegisPoint3 target_m;
    double sound_speed_m_s;
    double frequency_hz;
} AegisFocusRequest;

typedef struct {
    uint32_t capacity;       /* Input: elements allocated in both arrays. */
    uint32_t count;          /* Output: elements written, or required size. */
    double *delays_s;        /* Caller-owned relative start delays. */
    double *phases_rad;      /* Caller-owned phases wrapped to [0, 2*pi). */
} AegisFocusOutput;

/**
 * Fit time_s = time_offset_s + distance_m / sound_speed_m_s.
 *
 * At least two distinct distances are required when fit_time_offset is true;
 * an origin-constrained fit accepts one or more samples. Distances and times
 * must be finite and greater than zero and within the AEGIS_MAX_CALIBRATION_*
 * bounds. fit_time_offset must be exactly zero or one. On every error the
 * output structure remains in its documented zero state.
 */
AegisResult Aegis_EstimateSoundSpeed(
    const double *distances_m,
    const double *times_s,
    uint32_t sample_count,
    uint32_t fit_time_offset,
    AegisToFCalibration *out_calibration
);

/**
 * Compute direct-path relative delays and sinusoidal drive phases.
 *
 * The convention is cos(2*pi*f*t + phase_rad). If output capacity is too
 * small, no array elements are written, output->count receives the required
 * channel count, and AEGIS_ERR_BUFFER_TOO_SMALL is returned. The two output
 * arrays and the emitter-position array must not overlap; detected overlap is
 * rejected. Inputs requiring more than AEGIS_MAX_PHASE_CYCLES of relative
 * delay are rejected to preserve binary64 phase-reduction precision.
 */
AegisResult Aegis_ComputeFocusReference(
    const AegisFocusRequest *request,
    AegisFocusOutput *output
);

const char *Aegis_ResultString(AegisResult result);

#ifdef __cplusplus
}
#endif

#endif /* AEGIS_CORE_H */
