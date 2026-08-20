#include "aegis_core.h"

#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool aegis_positive_finite(double value) {
    return isfinite(value) && value > 0.0;
}

static bool aegis_in_closed_range(double value, double minimum, double maximum) {
    return isfinite(value) && value >= minimum && value <= maximum;
}

static bool aegis_point_finite(AegisPoint3 point) {
    return isfinite(point.x_m) && isfinite(point.y_m) && isfinite(point.z_m);
}

static bool aegis_ranges_overlap(
    const void *first,
    size_t first_size,
    const void *second,
    size_t second_size
) {
    const uintptr_t first_start = (uintptr_t)first;
    const uintptr_t second_start = (uintptr_t)second;
    uintptr_t first_end;
    uintptr_t second_end;

    if (UINTPTR_MAX - first_start < first_size ||
        UINTPTR_MAX - second_start < second_size) {
        return true;
    }
    first_end = first_start + first_size;
    second_end = second_start + second_size;
    return first_start < second_end && second_start < first_end;
}

AegisResult Aegis_EstimateSoundSpeed(
    const double *distances_m,
    const double *times_s,
    uint32_t sample_count,
    uint32_t fit_time_offset,
    AegisToFCalibration *out_calibration
) {
    uint32_t index;
    long double mean_distance = 0.0L;
    long double mean_time = 0.0L;
    long double denominator = 0.0L;
    long double numerator = 0.0L;
    long double slope_s_m;
    long double offset_s = 0.0L;
    long double residual_square_sum = 0.0L;
    double sound_speed_m_s;
    double rms_residual_s;

    if (out_calibration != NULL) {
        out_calibration->sound_speed_m_s = 0.0;
        out_calibration->time_offset_s = 0.0;
        out_calibration->rms_residual_s = 0.0;
        out_calibration->sample_count = 0U;
        out_calibration->fit_time_offset = 0U;
    }
    if (distances_m == NULL || times_s == NULL || out_calibration == NULL ||
        fit_time_offset > 1U) {
        return AEGIS_ERR_INVALID_PARAMS;
    }
    if (sample_count == 0U ||
        (fit_time_offset != 0U && sample_count < 2U)) {
        return AEGIS_ERR_INSUFFICIENT_SAMPLES;
    }

    for (index = 0U; index < sample_count; ++index) {
        if (!aegis_in_closed_range(
                distances_m[index], 0.0, AEGIS_MAX_CALIBRATION_DISTANCE_M
            ) || distances_m[index] == 0.0 ||
            !aegis_in_closed_range(
                times_s[index], 0.0, AEGIS_MAX_CALIBRATION_TIME_S
            ) || times_s[index] == 0.0) {
            return AEGIS_ERR_INVALID_PARAMS;
        }
        mean_distance += (long double)distances_m[index];
        mean_time += (long double)times_s[index];
    }
    mean_distance /= (long double)sample_count;
    mean_time /= (long double)sample_count;
    if (!isfinite(mean_distance) || !isfinite(mean_time)) {
        return AEGIS_ERR_NUMERIC;
    }

    if (fit_time_offset != 0U) {
        for (index = 0U; index < sample_count; ++index) {
            const long double distance_delta =
                (long double)distances_m[index] - mean_distance;
            denominator += distance_delta * distance_delta;
            numerator += distance_delta *
                ((long double)times_s[index] - mean_time);
        }
        if (!aegis_positive_finite(denominator)) {
            return AEGIS_ERR_SINGULAR_CALIBRATION;
        }
        slope_s_m = numerator / denominator;
        offset_s = mean_time - slope_s_m * mean_distance;
    } else {
        denominator = 0.0L;
        numerator = 0.0L;
        for (index = 0U; index < sample_count; ++index) {
            const long double distance = (long double)distances_m[index];
            denominator += distance * distance;
            numerator += distance * (long double)times_s[index];
        }
        if (!aegis_positive_finite(denominator)) {
            return AEGIS_ERR_SINGULAR_CALIBRATION;
        }
        slope_s_m = numerator / denominator;
    }

    if (!aegis_positive_finite(slope_s_m) || !isfinite(offset_s)) {
        return AEGIS_ERR_SINGULAR_CALIBRATION;
    }
    for (index = 0U; index < sample_count; ++index) {
        const long double residual = (long double)times_s[index] -
            (offset_s + slope_s_m * (long double)distances_m[index]);
        residual_square_sum += residual * residual;
    }
    if (!isfinite(residual_square_sum)) {
        return AEGIS_ERR_NUMERIC;
    }

    sound_speed_m_s = (double)(1.0L / slope_s_m);
    rms_residual_s = (double)sqrtl(
        residual_square_sum / (long double)sample_count
    );
    if (!aegis_in_closed_range(
            sound_speed_m_s,
            AEGIS_MIN_SOUND_SPEED_M_S,
            AEGIS_MAX_SOUND_SPEED_M_S
        ) || !isfinite((double)offset_s) || !isfinite(rms_residual_s)) {
        return AEGIS_ERR_NUMERIC;
    }
    out_calibration->sound_speed_m_s = sound_speed_m_s;
    out_calibration->time_offset_s = (double)offset_s;
    out_calibration->rms_residual_s = rms_residual_s;
    out_calibration->sample_count = sample_count;
    out_calibration->fit_time_offset = fit_time_offset;
    return AEGIS_SUCCESS;
}

AegisResult Aegis_ComputeFocusReference(
    const AegisFocusRequest *request,
    AegisFocusOutput *output
) {
    const double tau = 2.0 * acos(-1.0);
    double maximum_time_s = 0.0;
    size_t emitter_bytes;
    size_t output_bytes;
    uint32_t index;

    if (output != NULL) {
        output->count = 0U;
    }
    if (request == NULL || output == NULL ||
        request->emitter_positions_m == NULL || request->channel_count == 0U ||
        !aegis_point_finite(request->target_m) ||
        !aegis_in_closed_range(
            request->sound_speed_m_s,
            AEGIS_MIN_SOUND_SPEED_M_S,
            AEGIS_MAX_SOUND_SPEED_M_S
        ) || !aegis_in_closed_range(
            request->frequency_hz, 0.0, AEGIS_MAX_FREQUENCY_HZ
        ) || request->frequency_hz == 0.0) {
        return AEGIS_ERR_INVALID_PARAMS;
    }
    if (output->capacity < request->channel_count) {
        output->count = request->channel_count;
        return AEGIS_ERR_BUFFER_TOO_SMALL;
    }
    if (output->delays_s == NULL || output->phases_rad == NULL) {
        return AEGIS_ERR_INVALID_PARAMS;
    }
    if ((size_t)request->channel_count > SIZE_MAX / sizeof(AegisPoint3) ||
        (size_t)request->channel_count > SIZE_MAX / sizeof(double)) {
        return AEGIS_ERR_NUMERIC;
    }
    emitter_bytes = (size_t)request->channel_count * sizeof(AegisPoint3);
    output_bytes = (size_t)request->channel_count * sizeof(double);
    if ((uintptr_t)request->emitter_positions_m % _Alignof(AegisPoint3) != 0U ||
        (uintptr_t)output->delays_s % _Alignof(double) != 0U ||
        (uintptr_t)output->phases_rad % _Alignof(double) != 0U ||
        aegis_ranges_overlap(
            output->delays_s, output_bytes, output->phases_rad, output_bytes
        ) ||
        aegis_ranges_overlap(
            request->emitter_positions_m, emitter_bytes,
            output->delays_s, output_bytes
        ) ||
        aegis_ranges_overlap(
            request->emitter_positions_m, emitter_bytes,
            output->phases_rad, output_bytes
        )) {
        return AEGIS_ERR_INVALID_PARAMS;
    }
    for (index = 0U; index < request->channel_count; ++index) {
        const AegisPoint3 emitter = request->emitter_positions_m[index];
        double distance_m;
        double propagation_time_s;
        if (!aegis_point_finite(emitter)) {
            return AEGIS_ERR_INVALID_PARAMS;
        }
        distance_m = hypot(
            hypot(request->target_m.x_m - emitter.x_m,
                  request->target_m.y_m - emitter.y_m),
            request->target_m.z_m - emitter.z_m
        );
        if (!aegis_positive_finite(distance_m)) {
            return AEGIS_ERR_INVALID_PARAMS;
        }
        propagation_time_s = distance_m / request->sound_speed_m_s;
        if (!aegis_positive_finite(propagation_time_s)) {
            return AEGIS_ERR_NUMERIC;
        }
        if (propagation_time_s > maximum_time_s) {
            maximum_time_s = propagation_time_s;
        }
    }

    /* Validate every phase expression before writing any caller buffer. */
    for (index = 0U; index < request->channel_count; ++index) {
        const AegisPoint3 emitter = request->emitter_positions_m[index];
        const double distance_m = hypot(
            hypot(request->target_m.x_m - emitter.x_m,
                  request->target_m.y_m - emitter.y_m),
            request->target_m.z_m - emitter.z_m
        );
        const double delay_s = maximum_time_s -
            distance_m / request->sound_speed_m_s;
        const double phase_cycles = request->frequency_hz * delay_s;
        if (!isfinite(delay_s) || delay_s < 0.0 ||
            !isfinite(phase_cycles) || phase_cycles > AEGIS_MAX_PHASE_CYCLES) {
            return AEGIS_ERR_NUMERIC;
        }
    }

    for (index = 0U; index < request->channel_count; ++index) {
        const AegisPoint3 emitter = request->emitter_positions_m[index];
        const double distance_m = hypot(
            hypot(request->target_m.x_m - emitter.x_m,
                  request->target_m.y_m - emitter.y_m),
            request->target_m.z_m - emitter.z_m
        );
        const double delay_s = maximum_time_s -
            distance_m / request->sound_speed_m_s;
        const double phase_cycles = request->frequency_hz * delay_s;
        double phase_rad = fmod(-phase_cycles, 1.0) * tau;
        if (phase_rad < 0.0) {
            phase_rad += tau;
        }
        output->delays_s[index] = delay_s;
        output->phases_rad[index] = phase_rad == 0.0 ? 0.0 : phase_rad;
    }
    output->count = request->channel_count;
    return AEGIS_SUCCESS;
}

const char *Aegis_ResultString(AegisResult result) {
    switch (result) {
        case AEGIS_SUCCESS:
            return "success";
        case AEGIS_ERR_INVALID_PARAMS:
            return "invalid parameters";
        case AEGIS_ERR_INSUFFICIENT_SAMPLES:
            return "insufficient samples";
        case AEGIS_ERR_SINGULAR_CALIBRATION:
            return "singular calibration";
        case AEGIS_ERR_BUFFER_TOO_SMALL:
            return "buffer too small";
        case AEGIS_ERR_NUMERIC:
            return "numeric error";
        default:
            return "unknown result";
    }
}
