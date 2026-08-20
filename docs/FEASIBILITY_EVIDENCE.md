# Aegis-Acoustics 증거 매트릭스

이 문서는 프로젝트의 주장을 증거 수준별로 분리합니다. 시뮬레이션 통과를 하드웨어 성능으로 확대 해석하지 않는 것이 원칙입니다. 상세한 금지 주장과 안전·사업 한계는 권위 문서인 [`Aegis_Acoustics_B2B_Whitepaper.md`](Aegis_Acoustics_B2B_Whitepaper.md)를 따릅니다.

> **제품·고객 적용 판정: NO-GO.** 저장소에 포함된 Aegis 하드웨어 전기 위상·3D 음장·침착 저감·안전 실측은 0건입니다. 현재 허용되는 것은 300 nm부터 시작하는 축소 벤치 검증의 준비와 수행뿐이며, 제품 또는 물리 실현가능성 GO가 아닙니다. 10–50 nm 완전 차단, HVAC 대체와 wafer 이송은 NO-GO입니다.

`verified`는 코드 계산 재현, `passed=true`는 잠긴 한 데이터셋의 구현 규칙 통과만 의미합니다. `validated`는 추적 가능한 Aegis 하드웨어 증거가 있을 때만 사용하며 현재 해당되는 subsystem은 없습니다. `--report-only`의 exit 0도 보고서 생성 성공일 뿐 performance pass가 아닙니다.

## 증거 수준

- **코드 검증:** 정의한 수식과 입력에 대해 구현이 일관되며 자동 테스트가 통과함
- **합성 민감도/데모:** 명시한 가정값을 넣었을 때의 코드 출력. 입력 분포나 장치 성능을 측정한 것은 아님
- **로컬 벤치마크:** 현재 컴퓨터에서 실행시간 목표를 통과함. RTOS WCET 보장은 아님
- **외부 실험 근거:** 독립 연구가 유사 원리를 실험했으나 Aegis 장치를 검증한 것은 아님
- **하드웨어 미증명:** 실제 배열·가스·입자·웨이퍼 데이터가 필요함
- **현재 모델 비지지:** 현재 파라미터와 모델로는 해당 주장을 지지할 수 없음. 모든 가능한 구현을 반증한다는 뜻은 아님

## 주장별 상태

| 주장 | 상태 | 현재 증거 | 다음 게이트 |
|---|---|---|---|
| ToF에서 평균 음속을 계산할 수 있음 | 코드 검증 | 합성 거리·ToF 입력의 역산 테스트 | 교정된 마이크·온도센서와 실제 가스 측정 |
| 알려진 배열 좌표와 음속에서 상대 지연 계산 가능 | 코드 검증 | [`aegis_phase_calibration.py`](../simulation/aegis_phase_calibration.py)의 기하학 테스트 | 256채널 측정 위상과 예측 위상 비교 |
| 256채널 계산이 100 ms 미만 | 로컬 벤치마크 | 반복 실행의 median/p95/p99 보고 | 대상 IPC/FPGA/RTOS에서 WCET와 jitter 측정 |
| 위상 오차 민감도 | 합성 민감도 | 기본 가정 noise에서 2,000회 시행의 p95 최악 채널 오차 약 0.406°; noise는 실측 스펙이 아님 | 실측 noise·bias·drift·상관구조로 재적합하고 실제 256채널 위상 오차 측정 |
| 향후 256채널 전기 구동 출력 측정 데이터 분석 | 분석 파이프라인 검증 | [`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py)가 공통 circular offset 1개를 적합하고 p50/p95/p99/max/RMS를 보고. 공개된 experimental CSV는 없고 template은 synthetic이며 항상 `passed=false` | 교정 이력이 있는 계측기·공통 참조로 실제 256채널 회로를 반복 측정; acoustic-arrival/target field는 별도 분석 |
| 69.444 ns delay tick | 독립 설계 상한 | 40 kHz에서 1° 예산 전체를 양자화에만 배정한 상한; Monte Carlo에 양자화는 포함되지 않음 | 보정·클럭·driver·채널 오차에 예산을 배분한 뒤 더 작은 tick으로 재설계 |
| 가스 변경 뒤 초점이 복구됨 | 하드웨어 미증명 | 계산은 평균 음속 변화만 반영 | Air/N2에서 3D pressure scan 및 초점 오차 측정 |
| 이상적 정상파의 방사력·potential 추정 | 코드 검증·정량 외삽 불가 | [`aegis_radiation_force_feasibility.py`](../simulation/aegis_radiation_force_feasibility.py)의 단위 테스트. 기본 10–300 nm는 particle-continuum/경계층 검사를 통과하지 못함 | [`MODEL_SELECTION.md`](MODEL_SELECTION.md)의 병합 gate를 따르는 모델과 Aegis pressure/particle 측정 |
| 기체에서 약 150 nm 입자 조작 가능 | 외부 실험 근거 | Imani & Robert의 50–80 kHz 폐쇄형 공진 채널 실험. 조작은 차단·제거·wafer 침착 저감을 뜻하지 않음 | Aegis 형상에서 먼저 300 nm 대조시험; 통과 후에만 150 nm 검토 |
| 10–50 nm를 수 cm 거리에서 완전 차단 | **NO-GO** | 3 kPa 이상장 계산에서 선택한 안정 장벽에 부족하며 연속체 적용성 gap도 해결되지 않음 | 음향 단독 제품 주장은 중단하고 hybrid 방식과 실험으로 재정의 |
| 침착 표본수·power protocol | 사전 계획 계산 검증 | [`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py)가 독립 run endpoint, alpha 0.025 upper tail, 양 order 통과·일관성, Wilson MC 하한과 SD 민감도를 계산하고 locked input으로 결과를 재현 | pilot/assumed SD의 근거, actual percentile-bootstrap gate operating characteristics, 외부 서명·timestamp preregistration |
| paired 침착 분석기 | 코드 파이프라인 검증 | CSV/schema, paired log-ratio, `independent_run_id` cluster bootstrap, order 표현·일관성, 실험 범위·정확한 표본 배정을 묶은 machine-verified power lock, traceability·환경 span, 제한된 resample 수와 MC guard를 코드로 검사 | run ID의 실제 독립성, power input 가정의 진실성, 반복 blank 불확실성 모델과 실험 provenance |
| `deposition_trial_template.csv` 결과 | `demonstration_only` | `data_provenance=synthetic`이므로 수치 효과와 관계없이 `passed=false`; 합성 예제 | Aegis 성능 증거로 전환하지 않고 실험 provenance를 별도 확인 |
| 대형 wafer의 비접촉 부양 | 외부 실험 근거·Aegis 미증명 | 별도 near-field squeeze-film 연구가 존재 | sub-mm 장치로 분리해 높이·tilt·drop 시험 |
| HVAC 대체 또는 30% 에너지 절감 | **NO-GO** | 계산·하드웨어·감사 데이터 없음 | 현재 제품 주장에서 제외; 장래에는 fab baseline energy audit와 승인된 pilot가 필요 |
| 안전·규제·cleanroom/OEM 적합성 | **미평가·주장 금지** | Aegis 음향 노출·ESD·EMC·전기·열·가스·interlock·outgassing 시험 데이터 없음 | 장치별 위험 분석, 적용 규격 matrix와 독립 적합성 시험 |
| 수율·uptime·CAPEX/OPEX·ROI | **증거 없음** | fab baseline, system boundary, retrofit·유지보수·생산 데이터 없음 | 경계가 고정된 pilot와 경제성 감사; 한 device 결과의 OEM/fab 전이 금지 |
| C 참조 계산 API | 코드 검증 | [`aegis_core.c`](../sdk/aegis_core.c)의 stateless·allocation-free 구현, Python 수치 parity, strict C/C++ build·host ABI 테스트 | 센서 취득, transducer driver, RTOS 안전 상태 머신, 타겟 ABI, HIL |

## 재현

저장소 루트에서 다음 순서로 실행합니다.

```bash
python3 -m pip install -r requirements.txt
make verify
make phase-benchmark
make phase-uncertainty
make phase-measurement-example
make radiation-report
make deposition-power
make deposition-example
```

`make verify`는 strict C/C++ build·C/Python parity·ABI 테스트를 포함한 전체 unittest를 실행합니다. `requirements.txt`는 검증에 사용한 NumPy/Matplotlib 버전을 정확히 고정합니다. `make deposition-power`는 실행용이 아닌 example-only planning fixture를 재계산·검증하고, `make deposition-example`은 synthetic CSV로 `demonstration_only`/`passed=false` 보고서를 생성합니다. 명령 성공·`verified=true`·`--report-only` exit 0은 코드 또는 보고서 생성 성공일 뿐 장치 성능 게이트가 아닙니다. 개별 CLI 옵션은 각 명령의 `--help`로 확인합니다.

새 prospective protocol은 [`deposition_protocol_config.json`](../examples/deposition_protocol_config.json)을 복사해 `protocol.example_only=false`, 실제 protocol/device/rule ID와 실험 범위·가정을 정한 뒤 `aegis_deposition_power.py plan`으로 계획 문서를 만들고, 결과를 보기 전에 `lock`으로 사용하지 않은 경로에 고정한 후 `verify`합니다. 배포 fixture는 `example_only=true`, `execution_eligible=false`라서 acceptance 분석에 사용할 수 없습니다. 이 순서는 계산 재현 경로일 뿐 사전등록 시점을 자체 증명하지 않으므로 외부 서명·timestamp registry도 함께 사용해야 합니다.

검증 보고에는 Python/NumPy 버전, 입력 파라미터, 출력 JSON, commit hash와 실행 장비를 함께 기록해야 합니다.

### 로컬 탐색 실행(감사 기준선 아님)

2026-08-20에 Python 3.9.6/macOS arm64에서 256채널 계산을 1,000회 실행한 결과는 median **0.380 ms**, p95 **0.414 ms**, p99 **0.436 ms**, 관측 최대 **0.503 ms**였고 모든 관측 샘플이 100 ms 이내였습니다. 당시 commit hash와 raw JSON artifact가 함께 보존되지 않았으므로 이 숫자는 감사 가능한 역사적 baseline이 아니라 재실행 안내를 위한 탐색 관측입니다. 센서 취득·통신·FPGA/DAC·트랜스듀서 정착 시간이나 RTOS WCET의 증거도 아닙니다. 이후 기준선은 clean commit hash, 실행 장비·의존성, 원본 JSON을 함께 보존해야 합니다.

같은 날 `make phase-uncertainty`의 기본값(2,000 trials, seed 20260820, 40 kHz, timestamp noise σ=100 ns, 기준 거리 noise σ=50 µm)에서 `trial_max_absolute_rad.p95` 결과는 **0.007093 rad ≈ 0.406°**였습니다. noise는 서로 독립인 zero-mean Gaussian으로 가정했으며 Aegis 하드웨어에서 측정한 값이 아닙니다. 보고서의 `hardware_accuracy_validated` 및 `noise_parameters_measured_on_aegis_hardware`는 모두 `false`입니다. **69.444 ns**는 1° 위상 예산 전체를 양자화에만 쓴 독립 상한이며, 양자화 오차는 이 Monte Carlo에 합성되지 않았습니다.

## 256채널 전기 구동 위상 분석

[`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py)는 위상 계산기의 `cos(omega*t+phi)` 부호 규약에 맞춰 공통 트리거를 참조한 **전기 구동 출력**만 비교합니다. CSV는 `measurement_plane=electrical_drive_output`, `phase_reference_id`, `instrument_id`, `calibration_record_id`를 필수로 요구하며 target-microphone/acoustic-arrival 데이터를 거부합니다. 이 구분은 예측 구동 위상과 전파 후 도달 위상을 섞어 잘못 판정하는 것을 막습니다.

분석기는 측정−예측의 circular mean으로 전역 오프셋 하나를 제거한 후 상대 잔차를 계산합니다. 따라서 절대 위상·절대 timing을 검증하지 않으며 적합에 자유도 1개를 사용합니다. 실험 provenance, 0–255 정확한 채널 범위, 계측기 교정·사전 기준 self-attestation, p95/max 1° 이하의 임시 project cap을 모두 만족해야 좁은 상대-구동-위상 gate를 통과합니다. 이 cap은 장치 인증 기준이 아닙니다.

`phase_measurement_template.csv`의 256채널은 합성 데이터입니다. 수치 잔차가 거의 0이어도 `demonstration_only=true`, `single_run_relative_drive_phase_rule_passed=false`, `passed=false`, `device_performance_validated=false`로 남습니다. `passed`와 `device_relative_phase_gate_passed`는 호환 alias이며 장치 검증 의미가 아닙니다. 입력 SHA-256은 분석에 사용한 동일 byte snapshot에서 계산됩니다. 실제 초점 음압·3D field·사이드로브·음향 도달 위상은 이 분석의 범위 밖입니다.

## 침착 power 계획과 protocol lock

[`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py)는 CSV row가 아닌 각 `independent_run_id` 내 `mean(log(ON/OFF))`를 표본 단위로 둡니다. 귀무경계는 `H0: reduction <= minimum`이며, 현재 분석기의 중앙 95% CI 상단과 맞추기 위해 단측 upper-tail alpha 0.025를 사용합니다. 양 randomized order의 각 CI와 overall CI, order 일관성을 모두 통과할 joint power를 계획하며 order별 정규 근사 표본수를 절대 하한으로 삼습니다.

[`deposition_protocol_template.json`](../examples/deposition_protocol_template.json)은 300 nm 범위의 **software-reproducibility fixture이며 사전등록·실행용 protocol이 아닙니다.** Schema v3의 canonical SHA-256은 `0913b1318726ef19dfb966677c037d4ae9278a02a3d2f3089e5aaa7af0620507`이고, `example_only=true`, `execution_eligible=false`가 fingerprint 범위에 포함됩니다. 따라서 fixture의 `verified=true`는 결정론적 재계산·내용 일치만 뜻하며 deposition acceptance 분석기는 이 lock을 거부합니다. 예제 가정은 최소 저감 30%, 예상 저감 45%, log-ratio SD 0.35, target joint power 0.80입니다. seeded known-SD z surrogate는 **23 independent runs/order, 총 46 runs**을 계산합니다. 표본수 검색 stream의 추정 power는 0.83144(Wilson lower 0.82911), 별도 domain의 holdout surrogate stream은 0.82973(Wilson lower 0.82739)입니다. 최종 content-lock 가능 여부는 후자의 하한으로 판정해 같은 표본을 선택·검증하는 post-selection 문제를 줄입니다. SD를 1.25×로 높이면 35/order·총 70회, 1.5×이면 50/order·총 100회의 민감도 계획이 됩니다. 이 Monte Carlo는 **actual percentile-bootstrap gate의 power 검증이 아니며**, Wilson 구간은 surrogate Monte Carlo 계산 오차만 다룹니다. 예제 SD도 실측 Aegis 값이 아니므로 46회가 충분하거나 실험 성공 확률이 약 83%라고 말할 수 없습니다. 실제 lock에서는 pilot SD의 사전 UCB/assurance 또는 정당화된 보수 SD를 먼저 선택해야 합니다.

lock은 canonical planning input에서 전체 계획을 결정론적으로 다시 실행하고 SHA-256을 확인합니다. 변조 후 hash만 다시 계산한 모순 문서도 거부합니다. 그러나 fingerprint는 내용 동일성만 보여주며 작성자, 작성 시각, 결과 열람 전 등록, 실제 실험 준수를 증명하지 못합니다. 외부 서명·timestamp registry와 일탈 기록이 여전히 필요합니다.

## 침착 분석 결과의 해석

[`aegis_deposition_analysis.py`](../analysis/aegis_deposition_analysis.py)는 positive corrected count의 `log(ON/OFF)`를 paired block에서 계산한 뒤, 같은 `independent_run_id` 내 반복을 평균하고 독립 run을 동일 가중하여 cluster percentile bootstrap CI를 보고합니다. 게이트는 experimental provenance, 사전 기준 chronology self-attestation, 재계산된 locked power protocol, 10,000–1,000,000 bootstrap resamples, 정확한 총/order별 독립 run 수, order별 효과·일관성, traceability·환경 span과 MC 경계 guard를 검사합니다. locked protocol은 분석 옵션뿐 아니라 CSV의 장치·입자·가스·유량·노출·채집 면적·측정법·제외정책, 중단·대체 규칙과 `protocol_id`를 정확히 결합합니다. 초과 모집이나 다른 실험 범위에는 새 protocol이 필요합니다. day와 aerosol batch의 다양성은 보고하지만 이들의 effect를 추정하는 모델은 없습니다. 자동 테스트는 코드 경로와 계산 일관성을 검증할 뿐, run ID의 물리적 독립성·power input 가정의 진실성·실험 준수나 Aegis 침착 저감률을 검증하지 않습니다.

[`deposition_trial_template.csv`](../examples/deposition_trial_template.csv)의 숫자는 모두 합성이며 `data_provenance=synthetic`인 demonstration-only 예제입니다. 분석기는 수치 효과와 관계없이 `status=demonstration_only`, `dataset_rule_passed=false`, `device_performance_validated=false`를 보고합니다. 기존 `passed`, `analysis_pipeline_validated`, `performance_acceptance_gate_passed`, `hardware_acceptance_eligible`은 각각 명확한 새 필드의 compatibility alias로 표시됩니다. 합성 상태와 같은 선행 상태가 없는 experimental input에서도 `paired_subtract`는 반복 blank 불확실성을 모델링하지 않으므로 `diagnostic_only_blank_uncertainty_unmodelled`로 보고되며 gate를 통과할 수 없습니다. 예전 `--confirm-power-analysis`은 제거되었고 `--locked-protocol-json`이 필요합니다. `--confirm-prespecified-gate`는 chronology self-attestation으로 남아 있으며 fingerprint가 이 시점을 증명하지는 못합니다. 보고서는 `power_analysis_calculations_machine_verified=true`와 별개로 `power_analysis_inputs_validated_by_this_tool=false`, `power_analysis_input_values_authenticated=false`를 유지합니다. 실험 증거를 만들려면 최소한 다음이 필요합니다.

현재 acceptance planner는 `blank_policy=none`만 지원하고 실제 percentile-bootstrap gate operating characteristics도 검증하지 않았습니다. 따라서 향후 experimental input의 `passed=true`도 dataset-rule pass일 뿐 hardware-validation pass가 아니며 `device_performance_validated=false`가 유지됩니다.

1. 데이터를 보기 전에 primary endpoint, 최소 저감률, 제외, blank policy와 순서효과 분석을 프로토콜로 고정합니다.
2. pilot variance와 필요 power로 표본 수를 계획하고, 단순 CSV 행이 아닌 독립 day/aerosol run을 실험 단위로 삼습니다. device별 결과를 분리하고, 여러 device 일반화에는 별도 모델을 사용합니다.
3. ON/OFF 순서를 blocked randomization하고 양쪽 order의 최소 표본과 order별 효과 일관성을 확인합니다.
4. blank를 반복 측정하고 신호와 동일한 면적·노출 기준으로 정규화하며, blank 측정 불확실성을 CI에 전파합니다.
5. raw data, 무작위 스케줄, 일탈, calibration과 실행 환경의 provenance를 보존합니다.

## 허용되는 표현

- “256채널 상대 위상 지연 계산이 이 장비에서 측정된 p99 시간 내 완료됐다.”
- “실측값이 아닌 기본 합성 noise 가정에서 p95 최악 채널 상대 위상 오차가 약 0.406°였다.”
- “정해진 pressure의 이상적인 1차원 정상파 모델에서 입자 크기별 potential을 계산했다.”
- “C 참조 구현이 테스트 호스트에서 Python 결과와 수치적으로 일치했다.”
- “합성 침착 template로 CSV와 분석 파이프라인을 실행했다.”
- “외부 공진 채널 연구는 약 150 nm까지 기체 입자 조작 가능성을 보였다.”
- “Aegis 장치의 침착 저감률은 아직 측정되지 않았다.”

다음 표현은 하드웨어 게이트 전에는 사용하지 않습니다.

- “10–50 nm 파티클을 완전히 차단한다.”
- “합성 noise 민감도 통과로 실제 256채널 정확도가 검증됐다.”
- “69.444 ns tick만 맞추면 전체 1° 오차를 보장한다.”
- “합성 침착 template의 effect나 CI가 Aegis 저감률을 증명한다.”
- “C parity 테스트가 driver 또는 HIL을 검증했다.”
- “가스 종류와 무관하게 같은 성능을 낸다.”
- “완벽한 무마찰 wafer 이송을 제공한다.”
- “HVAC를 대체해 30% 이상 절감한다.”

## 최소 벤치 프로토콜

1. **장치:** 실제 배열, 반사체, 기준 마이크, 온도·압력·습도 센서와 밀폐 시험 챔버를 사용합니다.
2. **조건:** Air/N2, 여러 유량과 50/100/150/300 nm의 전하 관리된 표준 aerosol을 사용합니다.
3. **대조:** 음장 ON/OFF를 blocked randomization하고 순서별 효과와 carryover를 보고합니다.
4. **측정:** SMPS/CPC의 공간 분포와 300 mm witness wafer의 표면 침착 맵을 함께 기록합니다.
5. **부작용:** 재비산·다른 위치 재침착, 발열, wafer 진동, transducer particle adders, 초음파 누설을 측정합니다.
6. **통계 계획:** pilot variance에 기반한 power, 독립 day/device/aerosol run 수, 반복 blank와 불확실성 전파를 사전 정의합니다.
7. **판정:** 시험 전에 OEM과 목표 저감률·신뢰구간·허용 부작용·중단 기준을 합의합니다.

입자 저감과 위상 보정이 각각 통과한 뒤에만 통합 시험을 수행합니다. 웨이퍼 부양은 별도 near-field 프로젝트로 유지합니다.

## 외부 근거

- NIST/SEMATECH, [Paired Observations](https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm): paired 차이를 먼저 만들고 그 차이를 분석하는 실험 단위 해석의 기준
- NIST/SEMATECH, [Sample Sizes Required](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm): 알려진 표준편차를 가정한 정규 평균 검정의 표본수 근사 기준. 본 planner는 이를 order별 보수적 screening에만 사용하며 bootstrap gate의 정확한 power로 간주하지 않음
- H. Bruus, “Acoustofluidics 7: The acoustic radiation force on small particles,” *Lab on a Chip* 12, 1014–1021 (2012), DOI: [10.1039/C2LC21068A](https://doi.org/10.1039/C2LC21068A)
- R. J. Imani and E. Robert, “Estimation of acoustic forces on submicron aerosol particles in a standing wave field,” *Aerosol Science and Technology* 52, 57–68 (2018), DOI: [10.1080/02786826.2017.1383968](https://doi.org/10.1080/02786826.2017.1383968)
