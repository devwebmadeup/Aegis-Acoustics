/**
 * @file aegis_core.h
 * @brief Aegis-Acoustics: Adaptive Phase Calibration & Shield Generation SDK
 * @version 1.0.0
 * @copyright 2026 Aegis-Acoustics. All rights reserved. (Confidential)
 * 
 * [Architecture Note]
 * 본 SDK는 반도체 장비 제어기와의 통합을 위한 C-API를 제공합니다.
 * 실시간 운영체제(RTOS) 환경을 고려하여, API 내부에서 동적 메모리 할당을 수행하지 않으며,
 * 결과값을 담을 버퍼(Buffer)는 Host(장비사 프로그램)에서 사전에 할당하여 전달해야 합니다.
 */

#ifndef AEGIS_CORE_H
#define AEGIS_CORE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    AEGIS_SUCCESS = 0,
    AEGIS_ERR_INVALID_LICENSE = -1,
    AEGIS_ERR_NOT_INITIALIZED = -2,
    AEGIS_ERR_INVALID_PARAMS = -3,
    AEGIS_ERR_CALIBRATION_FAILED = -4
} AegisResult;

typedef enum {
    AEGIS_GAS_AIR = 0,     // 대기 (일반 EFEM 환경)
    AEGIS_GAS_N2 = 1,      // 고순도 질소 (FOUP 환경)
    AEGIS_GAS_HE = 2,      // 헬륨
    AEGIS_GAS_ARGON = 3    // 아르곤
} AegisGasType;

typedef struct {
    float ref_tof_us;      // 기준 마이크에서 측정된 ToF (마이크로초). 0이면 내부 추정치 사용.
    float temperature_c;   // 챔버 내부 현재 온도 (섭씨)
    AegisGasType gas_type; // 현재 공정 가스 종류
} AegisEnvironment;

typedef struct {
    float center_x_mm;     // 방어막 중심 X 좌표 (밀리미터)
    float center_y_mm;     // 방어막 중심 Y 좌표 (밀리미터)
    float z_height_mm;     // 웨이퍼 상단으로부터의 높이
    float radius_mm;       // 방어막(Dome)의 반경
    float intensity_pct;   // 방사압 강도 (0.0 ~ 100.0%)
} AegisTarget;

typedef struct {
    uint32_t num_transducers;    // 배열의 총 트랜스듀서 개수 (예: 256)
    float* out_phase_delays_us;  // [Host Pre-allocated] 각 채널별 위상 지연 시간 (마이크로초)
    float* out_amplitudes;       // [Host Pre-allocated] 각 채널별 진폭 제어값 (0.0 ~ 1.0)
} AegisPhaseMatrix;

AegisResult Aegis_Initialize(const char* license_key, uint32_t num_transducers);
AegisResult Aegis_CalibrateEnvironment(const AegisEnvironment* env, float* out_current_sos_mps);
AegisResult Aegis_ComputeShieldPhase(const AegisTarget* target, AegisPhaseMatrix* matrix);
void Aegis_Shutdown();

#ifdef __cplusplus
}
#endif

#endif // AEGIS_CORE_H
