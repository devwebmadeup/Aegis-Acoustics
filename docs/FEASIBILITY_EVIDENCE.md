# Aegis-Acoustics 증거 매트릭스 / Evidence Matrix

이 문서는 프로젝트의 주장을 증거 수준별로 분리합니다. 시뮬레이션 통과를 하드웨어 성능으로 확대 해석하지 않는 것이 원칙입니다. 상세한 금지 주장과 안전·사업 한계는 권위 문서인 [`Aegis_Acoustics_B2B_Whitepaper.md`](Aegis_Acoustics_B2B_Whitepaper.md)를 따릅니다.

This document separates the project's claims by evidence level. The governing principle is that a passing simulation is never read as hardware performance. Detailed prohibited claims and safety/business limitations follow the authoritative document, [`Aegis_Acoustics_B2B_Whitepaper.md`](Aegis_Acoustics_B2B_Whitepaper.md).

> **제품·고객 적용 판정: NO-GO.** 저장소에 포함된 Aegis 하드웨어 전기 위상·3D 음장·침착 저감·안전 실측은 0건입니다. 현재 허용되는 것은 300 nm부터 시작하는 축소 벤치 검증의 준비와 수행뿐이며, 제품 또는 물리 실현가능성 GO가 아닙니다. 10–50 nm 완전 차단, HVAC 대체와 wafer 이송은 NO-GO입니다.
>
> **Product/customer-application verdict: NO-GO.** The repository contains zero Aegis-hardware measurements of electrical phase, 3D acoustic field, deposition reduction, or safety. What is currently permitted is only preparing and running a reduced-scale bench validation starting at 300 nm — this is not a GO on the product or on physical feasibility. Full 10-50 nm exclusion, HVAC replacement, and wafer transport are NO-GO.

`verified`는 코드 계산 재현, `passed=true`는 잠긴 한 데이터셋의 구현 규칙 통과만 의미합니다. `validated`는 추적 가능한 Aegis 하드웨어 증거가 있을 때만 사용하며 현재 해당되는 subsystem은 없습니다. `--report-only`의 exit 0도 보고서 생성 성공일 뿐 performance pass가 아닙니다.

`verified` means only that a code calculation was reproduced; `passed=true` means only that one locked dataset satisfied an implemented rule. `validated` is used only when traceable Aegis hardware evidence exists, and no subsystem currently qualifies. An exit code of 0 from `--report-only` likewise means only that a report was generated successfully, not a performance pass.

## 증거 수준 / Evidence levels

- **코드 검증 / Code-verified:** 정의한 수식과 입력에 대해 구현이 일관되며 자동 테스트가 통과함 — *the implementation is internally consistent for the defined formulas/inputs and automated tests pass.*
- **합성 민감도/데모 / Synthetic sensitivity or demo:** 명시한 가정값을 넣었을 때의 코드 출력. 입력 분포나 장치 성능을 측정한 것은 아님 — *code output under stated assumed inputs; it does not measure input distributions or device performance.*
- **로컬 벤치마크 / Local benchmark:** 현재 컴퓨터에서 실행시간 목표를 통과함. RTOS WCET 보장은 아님 — *runtime targets pass on the current machine; not an RTOS WCET guarantee.*
- **외부 실험 근거 / External experimental evidence:** 독립 연구가 유사 원리를 실험했으나 Aegis 장치를 검증한 것은 아님 — *an independent study tested a similar principle, but it does not validate the Aegis device.*
- **하드웨어 미증명 / Hardware-unproven:** 실제 배열·가스·입자·웨이퍼 데이터가 필요함 — *requires real array, gas, particle, and wafer data.*
- **현재 모델 비지지 / Not supported by the current model:** 현재 파라미터와 모델로는 해당 주장을 지지할 수 없음. 모든 가능한 구현을 반증한다는 뜻은 아님 — *the current parameters and model cannot support the claim; this does not disprove every possible future implementation.*

## 주장별 상태 / Status by claim

| 주장 / Claim | 상태 / Status | 현재 증거 / Current evidence | 다음 게이트 / Next gate |
|---|---|---|---|
| ToF에서 평균 음속을 계산할 수 있음<br>Average sound speed can be computed from ToF | 코드 검증<br>Code-verified | 합성 거리·ToF 입력의 역산 테스트<br>Inversion tests on synthetic distance/ToF inputs | 교정된 마이크·온도센서와 실제 가스 측정<br>Real gas measurements with a calibrated microphone/temperature sensor |
| 알려진 배열 좌표와 음속에서 상대 지연 계산 가능<br>Relative delays computable from known array coordinates and sound speed | 코드 검증<br>Code-verified | [`aegis_phase_calibration.py`](../simulation/aegis_phase_calibration.py)의 기하학 테스트<br>Geometry tests in [`aegis_phase_calibration.py`](../simulation/aegis_phase_calibration.py) | 256채널 측정 위상과 예측 위상 비교<br>Compare measured vs. predicted phase across all 256 channels |
| 256채널 계산이 100 ms 미만<br>256-channel computation under 100 ms | 로컬 벤치마크<br>Local benchmark | 반복 실행의 median/p95/p99 보고<br>Reported median/p95/p99 over repeated runs | 대상 IPC/FPGA/RTOS에서 WCET와 jitter 측정<br>Measure WCET and jitter on the target IPC/FPGA/RTOS |
| 위상 오차 민감도<br>Phase-error sensitivity | 합성 민감도<br>Synthetic sensitivity | 기본 가정 noise에서 2,000회 시행의 p95 최악 채널 오차 약 0.406°; noise는 실측 스펙이 아님<br>p95 worst-channel error over 2,000 trials under default assumed noise is about 0.406°; the noise is not a measured spec | 실측 noise·bias·drift·상관구조로 재적합하고 실제 256채널 위상 오차 측정<br>Refit with measured noise/bias/drift/correlation and measure real 256-channel phase error |
| 향후 256채널 전기 구동 출력 측정 데이터 분석<br>Future analysis of 256-channel electrical drive-output measurements | 분석 파이프라인 검증<br>Analysis-pipeline verified | [`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py)가 공통 circular offset 1개를 적합하고 p50/p95/p99/max/RMS를 보고. 공개된 experimental CSV는 없고 template은 synthetic이며 항상 `passed=false`<br>[`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py) fits one common circular offset and reports p50/p95/p99/max/RMS. No experimental CSV is published; the template is synthetic and always `passed=false` | 교정 이력이 있는 계측기·공통 참조로 실제 256채널 회로를 반복 측정; acoustic-arrival/target field는 별도 분석<br>Repeated real 256-channel measurements with calibrated instruments and a common reference; acoustic-arrival/target field is a separate analysis |
| 69.444 ns delay tick | 독립 설계 상한<br>Independent design ceiling | 40 kHz에서 1° 예산 전체를 양자화에만 배정한 상한; Monte Carlo에 양자화는 포함되지 않음<br>A ceiling that allocates the entire 1° budget at 40 kHz to quantization alone; quantization is not included in the Monte Carlo | 보정·클럭·driver·채널 오차에 예산을 배분한 뒤 더 작은 tick으로 재설계<br>Redesign with a smaller tick after allocating budget across calibration/clock/driver/channel errors |
| 가스 변경 뒤 초점이 복구됨<br>Focus recovers after a gas change | 하드웨어 미증명<br>Hardware-unproven | 계산은 평균 음속 변화만 반영<br>The calculation reflects only the change in average sound speed | Air/N2에서 3D pressure scan 및 초점 오차 측정<br>3D pressure scan and focus-error measurement in Air/N2 |
| 이상적 정상파의 방사력·potential 추정<br>Radiation-force/potential estimate for an ideal standing wave | 코드 검증·정량 외삽 불가<br>Code-verified, not quantitatively extrapolable | [`aegis_radiation_force_feasibility.py`](../simulation/aegis_radiation_force_feasibility.py)의 단위 테스트. 기본 10–300 nm는 particle-continuum/경계층 검사를 통과하지 못함<br>Unit tests in [`aegis_radiation_force_feasibility.py`](../simulation/aegis_radiation_force_feasibility.py). The default 10-300 nm range fails the particle-continuum/boundary-layer applicability check | [`MODEL_SELECTION.md`](MODEL_SELECTION.md)의 병합 gate를 따르는 모델과 Aegis pressure/particle 측정<br>A model that follows the merge gate in [`MODEL_SELECTION.md`](MODEL_SELECTION.md), plus Aegis pressure/particle measurements |
| 기체에서 약 150 nm 입자 조작 가능<br>~150 nm particle manipulation is possible in gas | 외부 실험 근거<br>External experimental evidence | Imani & Robert의 50–80 kHz 폐쇄형 공진 채널 실험. 조작은 차단·제거·wafer 침착 저감을 뜻하지 않음<br>Imani & Robert's 50-80 kHz closed resonant-channel experiment. "Manipulation" does not mean exclusion, removal, or wafer deposition reduction | Aegis 형상에서 먼저 300 nm 대조시험; 통과 후에만 150 nm 검토<br>First a 300 nm controlled trial in the Aegis geometry; consider 150 nm only after passing |
| 10–50 nm를 수 cm 거리에서 완전 차단<br>Full exclusion of 10-50 nm at a multi-cm distance | **NO-GO** | 3 kPa 이상장 계산에서 선택한 안정 장벽에 부족하며 연속체 적용성 gap도 해결되지 않음<br>Falls short of the chosen stability barrier in the 3 kPa ideal-field calculation, and the continuum-applicability gap is also unresolved | 음향 단독 제품 주장은 중단하고 hybrid 방식과 실험으로 재정의<br>Stop the acoustics-only product claim and redefine it via a hybrid approach and experiments |
| 침착 표본수·power protocol<br>Deposition sample-size/power protocol | 사전 계획 계산 검증<br>Pre-registration calculation verified | [`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py)가 독립 run endpoint, alpha 0.025 upper tail, 양 order 통과·일관성, Wilson MC 하한과 SD 민감도를 계산하고 locked input으로 결과를 재현<br>[`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py) computes independent-run endpoints, an alpha 0.025 upper tail, pass/consistency across both orders, a Wilson MC lower bound, and SD sensitivity, and reproduces results from a locked input | pilot/assumed SD의 근거, actual percentile-bootstrap gate operating characteristics, 외부 서명·timestamp preregistration<br>Justification for pilot/assumed SD, the actual percentile-bootstrap gate's operating characteristics, external signed/timestamped preregistration |
| paired 침착 분석기<br>Paired deposition analyzer | 코드 파이프라인 검증<br>Code-pipeline verified | CSV/schema, paired log-ratio, `independent_run_id` cluster bootstrap, order 표현·일관성, 실험 범위·정확한 표본 배정을 묶은 machine-verified power lock, traceability·환경 span, 제한된 resample 수와 MC guard를 코드로 검사<br>The code checks CSV/schema, paired log-ratio, `independent_run_id` cluster bootstrap, order representation/consistency, a machine-verified power lock binding experiment scope and exact sample allocation, traceability/environment span, and a bounded resample count with an MC guard | run ID의 실제 독립성, power input 가정의 진실성, 반복 blank 불확실성 모델과 실험 provenance<br>Actual independence of run IDs, truthfulness of power-input assumptions, a repeated-blank uncertainty model, and experiment provenance |
| `deposition_trial_template.csv` 결과<br>`deposition_trial_template.csv` results | `demonstration_only` | `data_provenance=synthetic`이므로 수치 효과와 관계없이 `passed=false`; 합성 예제<br>Because `data_provenance=synthetic`, `passed=false` regardless of the numeric effect; a synthetic example | Aegis 성능 증거로 전환하지 않고 실험 provenance를 별도 확인<br>Verify experiment provenance separately, without converting it into Aegis performance evidence |
| 대형 wafer의 비접촉 부양<br>Non-contact levitation of a large wafer | 외부 실험 근거·Aegis 미증명<br>External experimental evidence; Aegis-unproven | 별도 near-field squeeze-film 연구가 존재<br>A separate near-field squeeze-film literature exists | sub-mm 장치로 분리해 높이·tilt·drop 시험<br>Separate sub-mm-scale device testing for height/tilt/drop |
| HVAC 대체 또는 30% 에너지 절감<br>HVAC replacement or 30% energy savings | **NO-GO** | 계산·하드웨어·감사 데이터 없음<br>No calculation, hardware, or audit data | 현재 제품 주장에서 제외; 장래에는 fab baseline energy audit와 승인된 pilot가 필요<br>Excluded from current product claims; a future claim would need a fab baseline energy audit and an approved pilot |
| 안전·규제·cleanroom/OEM 적합성<br>Safety/regulatory/cleanroom/OEM compliance | **미평가·주장 금지**<br>**Unassessed, claims prohibited** | Aegis 음향 노출·ESD·EMC·전기·열·가스·interlock·outgassing 시험 데이터 없음<br>No Aegis test data for acoustic exposure, ESD, EMC, electrical, thermal, gas, interlock, or outgassing | 장치별 위험 분석, 적용 규격 matrix와 독립 적합성 시험<br>A per-device risk analysis, an applicable-standards matrix, and independent compliance testing |
| 수율·uptime·CAPEX/OPEX·ROI<br>Yield/uptime/CAPEX-OPEX/ROI | **증거 없음**<br>**No evidence** | fab baseline, system boundary, retrofit·유지보수·생산 데이터 없음<br>No fab baseline, system boundary, retrofit/maintenance/production data | 경계가 고정된 pilot와 경제성 감사; 한 device 결과의 OEM/fab 전이 금지<br>A pilot with a fixed system boundary and an economic audit; results from one device must not be transferred to another OEM/fab |
| C 참조 계산 API<br>C reference calculation API | 코드 검증<br>Code-verified | [`aegis_core.c`](../sdk/aegis_core.c)의 stateless·allocation-free 구현, Python 수치 parity, strict C/C++ build·host ABI 테스트<br>The stateless, allocation-free implementation in [`aegis_core.c`](../sdk/aegis_core.c), Python numerical parity, and strict C/C++ build/host-ABI tests | 센서 취득, transducer driver, RTOS 안전 상태 머신, 타겟 ABI, HIL<br>Sensor acquisition, a transducer driver, an RTOS safety state machine, the target ABI, and HIL |

## 재현 / Reproduction

저장소 루트에서 다음 순서로 실행합니다.

Run the following in order from the repository root.

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

`make verify` runs the full unittest suite, including strict C/C++ builds, C/Python parity, and ABI tests. `requirements.txt` pins the exact NumPy/Matplotlib versions used for verification. `make deposition-power` recomputes and verifies a non-executable, example-only planning fixture; `make deposition-example` generates a `demonstration_only`/`passed=false` report from a synthetic CSV. Command success, `verified=true`, and an exit code of 0 from `--report-only` mean only that code ran or a report was generated — never a device-performance gate. See each command's `--help` for individual CLI options.

새 prospective protocol은 [`deposition_protocol_config.json`](../examples/deposition_protocol_config.json)을 복사해 `protocol.example_only=false`, 실제 protocol/device/rule ID와 실험 범위·가정을 정한 뒤 `aegis_deposition_power.py plan`으로 계획 문서를 만들고, 결과를 보기 전에 `lock`으로 사용하지 않은 경로에 고정한 후 `verify`합니다. 배포 fixture는 `example_only=true`, `execution_eligible=false`라서 acceptance 분석에 사용할 수 없습니다. 이 순서는 계산 재현 경로일 뿐 사전등록 시점을 자체 증명하지 않으므로 외부 서명·timestamp registry도 함께 사용해야 합니다.

For a new prospective protocol, copy [`deposition_protocol_config.json`](../examples/deposition_protocol_config.json), set `protocol.example_only=false` with real protocol/device/rule IDs and experiment scope/assumptions, produce a planning document with `aegis_deposition_power.py plan`, lock it to an unused path with `lock` before looking at results, and then `verify`. The shipped fixture has `example_only=true` and `execution_eligible=false`, so it cannot be used for an acceptance analysis. This sequence is only a computational-reproduction path and does not itself prove the preregistration timestamp, so an external signature/timestamp registry must also be used.

검증 보고에는 Python/NumPy 버전, 입력 파라미터, 출력 JSON, commit hash와 실행 장비를 함께 기록해야 합니다.

A verification report must also record the Python/NumPy version, input parameters, output JSON, commit hash, and execution hardware.

### 로컬 탐색 실행(감사 기준선 아님) / Local exploratory run (not an audit baseline)

2026-08-20에 Python 3.9.6/macOS arm64에서 256채널 계산을 1,000회 실행한 결과는 median **0.380 ms**, p95 **0.414 ms**, p99 **0.436 ms**, 관측 최대 **0.503 ms**였고 모든 관측 샘플이 100 ms 이내였습니다. 당시 commit hash와 raw JSON artifact가 함께 보존되지 않았으므로 이 숫자는 감사 가능한 역사적 baseline이 아니라 재실행 안내를 위한 탐색 관측입니다. 센서 취득·통신·FPGA/DAC·트랜스듀서 정착 시간이나 RTOS WCET의 증거도 아닙니다. 이후 기준선은 clean commit hash, 실행 장비·의존성, 원본 JSON을 함께 보존해야 합니다.

On 2026-08-20, running the 256-channel computation 1,000 times on Python 3.9.6/macOS arm64 produced a median of **0.380 ms**, p95 of **0.414 ms**, p99 of **0.436 ms**, and an observed maximum of **0.503 ms**, with every observed sample under 100 ms. Because the commit hash and raw JSON artifact were not preserved alongside it, this number is an exploratory observation to guide re-runs, not an auditable historical baseline. It is also not evidence of sensor acquisition, communication, FPGA/DAC, transducer settling time, or RTOS WCET. Future baselines must preserve the clean commit hash, execution hardware/dependencies, and the raw JSON together.

같은 날 `make phase-uncertainty`의 기본값(2,000 trials, seed 20260820, 40 kHz, timestamp noise σ=100 ns, 기준 거리 noise σ=50 µm)에서 `trial_max_absolute_rad.p95` 결과는 **0.007093 rad ≈ 0.406°**였습니다. noise는 서로 독립인 zero-mean Gaussian으로 가정했으며 Aegis 하드웨어에서 측정한 값이 아닙니다. 보고서의 `hardware_accuracy_validated` 및 `noise_parameters_measured_on_aegis_hardware`는 모두 `false`입니다. **69.444 ns**는 1° 위상 예산 전체를 양자화에만 쓴 독립 상한이며, 양자화 오차는 이 Monte Carlo에 합성되지 않았습니다.

On the same day, `make phase-uncertainty` with its defaults (2,000 trials, seed 20260820, 40 kHz, timestamp noise sigma=100 ns, reference-distance noise sigma=50 micrometers) produced a `trial_max_absolute_rad.p95` of **0.007093 rad, approx. 0.406°**. The noise was assumed to be mutually independent zero-mean Gaussian and is not a value measured on Aegis hardware. The report's `hardware_accuracy_validated` and `noise_parameters_measured_on_aegis_hardware` are both `false`. **69.444 ns** is an independent ceiling that spends the entire 1° phase budget on quantization alone; quantization error is not composited into this Monte Carlo.

## 256채널 전기 구동 위상 분석 / 256-channel electrical drive-phase analysis

[`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py)는 위상 계산기의 `cos(omega*t+phi)` 부호 규약에 맞춰 공통 트리거를 참조한 **전기 구동 출력**만 비교합니다. CSV는 `measurement_plane=electrical_drive_output`, `phase_reference_id`, `instrument_id`, `calibration_record_id`를 필수로 요구하며 target-microphone/acoustic-arrival 데이터를 거부합니다. 이 구분은 예측 구동 위상과 전파 후 도달 위상을 섞어 잘못 판정하는 것을 막습니다.

[`aegis_phase_measurement_analysis.py`](../analysis/aegis_phase_measurement_analysis.py) compares only the **electrical drive output**, referenced to a common trigger and matched to the phase calculator's `cos(omega*t+phi)` sign convention. The CSV requires `measurement_plane=electrical_drive_output`, `phase_reference_id`, `instrument_id`, and `calibration_record_id`, and it rejects target-microphone/acoustic-arrival data. This separation prevents mistakenly mixing predicted drive phase with post-propagation arrival phase.

분석기는 측정−예측의 circular mean으로 전역 오프셋 하나를 제거한 후 상대 잔차를 계산합니다. 따라서 절대 위상·절대 timing을 검증하지 않으며 적합에 자유도 1개를 사용합니다. 실험 provenance, 0–255 정확한 채널 범위, 계측기 교정·사전 기준 self-attestation, p95/max 1° 이하의 임시 project cap을 모두 만족해야 좁은 상대-구동-위상 gate를 통과합니다. 이 cap은 장치 인증 기준이 아닙니다.

The analyzer removes a single global offset via the circular mean of measured-minus-predicted values, then computes the relative residual. It therefore does not validate absolute phase or absolute timing, and the fit spends one degree of freedom. Passing the narrow relative-drive-phase gate requires satisfying experiment provenance, the exact 0-255 channel range, instrument-calibration/pre-specification self-attestation, and a provisional project cap of p95/max under 1°. This cap is not a device-certification standard.

`phase_measurement_template.csv`의 256채널은 합성 데이터입니다. 수치 잔차가 거의 0이어도 `demonstration_only=true`, `single_run_relative_drive_phase_rule_passed=false`, `passed=false`, `device_performance_validated=false`로 남습니다. `passed`와 `device_relative_phase_gate_passed`는 호환 alias이며 장치 검증 의미가 아닙니다. 입력 SHA-256은 분석에 사용한 동일 byte snapshot에서 계산됩니다. 실제 초점 음압·3D field·사이드로브·음향 도달 위상은 이 분석의 범위 밖입니다.

The 256 channels in `phase_measurement_template.csv` are synthetic. Even with a near-zero numeric residual, it remains `demonstration_only=true`, `single_run_relative_drive_phase_rule_passed=false`, `passed=false`, and `device_performance_validated=false`. `passed` and `device_relative_phase_gate_passed` are compatibility aliases and do not carry device-validation meaning. The input SHA-256 is computed from the exact byte snapshot used in the analysis. Actual focal pressure, the 3D field, sidelobes, and acoustic-arrival phase are outside the scope of this analysis.

## 침착 power 계획과 protocol lock / Deposition power planning and protocol lock

[`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py)는 CSV row가 아닌 각 `independent_run_id` 내 `mean(log(ON/OFF))`를 표본 단위로 둡니다. 귀무경계는 `H0: reduction <= minimum`이며, 현재 분석기의 중앙 95% CI 상단과 맞추기 위해 단측 upper-tail alpha 0.025를 사용합니다. 양 randomized order의 각 CI와 overall CI, order 일관성을 모두 통과할 joint power를 계획하며 order별 정규 근사 표본수를 절대 하한으로 삼습니다.

[`aegis_deposition_power.py`](../analysis/aegis_deposition_power.py) treats `mean(log(ON/OFF))` within each `independent_run_id` — not the CSV row — as the sampling unit. The null boundary is `H0: reduction <= minimum`, using a one-sided upper-tail alpha of 0.025 to match the current analyzer's central 95% CI upper bound. It plans joint power to pass both randomized orders' individual CIs, the overall CI, and order consistency, treating the per-order normal-approximation sample size as an absolute floor.

[`deposition_protocol_template.json`](../examples/deposition_protocol_template.json)은 300 nm 범위의 **software-reproducibility fixture이며 사전등록·실행용 protocol이 아닙니다.** Schema v3의 canonical SHA-256은 `0913b1318726ef19dfb966677c037d4ae9278a02a3d2f3089e5aaa7af0620507`이고, `example_only=true`, `execution_eligible=false`가 fingerprint 범위에 포함됩니다. 따라서 fixture의 `verified=true`는 결정론적 재계산·내용 일치만 뜻하며 deposition acceptance 분석기는 이 lock을 거부합니다. 예제 가정은 최소 저감 30%, 예상 저감 45%, log-ratio SD 0.35, target joint power 0.80입니다. seeded known-SD z surrogate는 **23 independent runs/order, 총 46 runs**을 계산합니다. 표본수 검색 stream의 추정 power는 0.83144(Wilson lower 0.82911), 별도 domain의 holdout surrogate stream은 0.82973(Wilson lower 0.82739)입니다. 최종 content-lock 가능 여부는 후자의 하한으로 판정해 같은 표본을 선택·검증하는 post-selection 문제를 줄입니다. SD를 1.25×로 높이면 35/order·총 70회, 1.5×이면 50/order·총 100회의 민감도 계획이 됩니다. 이 Monte Carlo는 **actual percentile-bootstrap gate의 power 검증이 아니며**, Wilson 구간은 surrogate Monte Carlo 계산 오차만 다룹니다. 예제 SD도 실측 Aegis 값이 아니므로 46회가 충분하거나 실험 성공 확률이 약 83%라고 말할 수 없습니다. 실제 lock에서는 pilot SD의 사전 UCB/assurance 또는 정당화된 보수 SD를 먼저 선택해야 합니다.

[`deposition_protocol_template.json`](../examples/deposition_protocol_template.json) is a 300 nm-scoped **software-reproducibility fixture, not a preregistered, execution-ready protocol.** The Schema v3 canonical SHA-256 is `0913b1318726ef19dfb966677c037d4ae9278a02a3d2f3089e5aaa7af0620507`, with `example_only=true` and `execution_eligible=false` included in the fingerprint scope. Consequently, `verified=true` for the fixture means only deterministic recomputation and content match, and the deposition acceptance analyzer rejects this lock. The example assumptions are a minimum reduction of 30%, an assumed reduction of 45%, a log-ratio SD of 0.35, and a target joint power of 0.80. The seeded known-SD z-surrogate computes **23 independent runs/order, 46 runs total**. The estimated power from the sample-size search stream is 0.83144 (Wilson lower 0.82911); a separate-domain holdout surrogate stream gives 0.82973 (Wilson lower 0.82739). Lock eligibility is decided on the latter's lower bound, to reduce the post-selection problem of selecting and validating on the same sample. Raising SD by 1.25x gives a sensitivity plan of 35/order (70 total); by 1.5x, 50/order (100 total). This Monte Carlo is **not a power validation of the actual percentile-bootstrap gate**, and the Wilson interval addresses only the surrogate Monte Carlo's computational error. The example SD is also not a measured Aegis value, so it cannot be said that 46 runs are sufficient or that the experiment's success probability is about 83%. An actual lock must first select either a pre-specified UCB/assurance on the pilot SD or a justified conservative SD.

lock은 canonical planning input에서 전체 계획을 결정론적으로 다시 실행하고 SHA-256을 확인합니다. 변조 후 hash만 다시 계산한 모순 문서도 거부합니다. 그러나 fingerprint는 내용 동일성만 보여주며 작성자, 작성 시각, 결과 열람 전 등록, 실제 실험 준수를 증명하지 못합니다. 외부 서명·timestamp registry와 일탈 기록이 여전히 필요합니다.

The lock deterministically re-runs the entire plan from the canonical planning input and verifies the SHA-256. It also rejects a self-contradicting document whose hash was merely recomputed after tampering. However, the fingerprint shows only content identity — it does not prove authorship, time of writing, registration before results were viewed, or actual experimental compliance. An external signature/timestamp registry and a deviation log are still required.

## 침착 분석 결과의 해석 / Interpreting deposition-analysis results

[`aegis_deposition_analysis.py`](../analysis/aegis_deposition_analysis.py)는 positive corrected count의 `log(ON/OFF)`를 paired block에서 계산한 뒤, 같은 `independent_run_id` 내 반복을 평균하고 독립 run을 동일 가중하여 cluster percentile bootstrap CI를 보고합니다. 게이트는 experimental provenance, 사전 기준 chronology self-attestation, 재계산된 locked power protocol, 10,000–1,000,000 bootstrap resamples, 정확한 총/order별 독립 run 수, order별 효과·일관성, traceability·환경 span과 MC 경계 guard를 검사합니다. locked protocol은 분석 옵션뿐 아니라 CSV의 장치·입자·가스·유량·노출·채집 면적·측정법·제외정책, 중단·대체 규칙과 `protocol_id`를 정확히 결합합니다. 초과 모집이나 다른 실험 범위에는 새 protocol이 필요합니다. day와 aerosol batch의 다양성은 보고하지만 이들의 effect를 추정하는 모델은 없습니다. 자동 테스트는 코드 경로와 계산 일관성을 검증할 뿐, run ID의 물리적 독립성·power input 가정의 진실성·실험 준수나 Aegis 침착 저감률을 검증하지 않습니다.

[`aegis_deposition_analysis.py`](../analysis/aegis_deposition_analysis.py) computes `log(ON/OFF)` of the positive corrected count within paired blocks, averages repeats within the same `independent_run_id`, weights independent runs equally, and reports a cluster percentile-bootstrap CI. The gate checks experimental provenance, pre-specification chronology self-attestation, a recomputed locked power protocol, 10,000-1,000,000 bootstrap resamples, the exact total/per-order independent run count, per-order effect/consistency, traceability/environment span, and an MC-boundary guard. The locked protocol binds not just analysis options but also the CSV's device/particle/gas/flow rate/exposure/collection area/measurement method/exclusion policy, stop/substitution rules, and `protocol_id` exactly. Over-enrollment or a different experiment scope requires a new protocol. Day and aerosol-batch diversity are reported, but there is no model estimating their effect. Automated tests verify only the code path and computational consistency — not the physical independence of run IDs, the truthfulness of power-input assumptions, experimental compliance, or the Aegis deposition-reduction rate.

[`deposition_trial_template.csv`](../examples/deposition_trial_template.csv)의 숫자는 모두 합성이며 `data_provenance=synthetic`인 demonstration-only 예제입니다. 분석기는 수치 효과와 관계없이 `status=demonstration_only`, `dataset_rule_passed=false`, `device_performance_validated=false`를 보고합니다. 기존 `passed`, `analysis_pipeline_validated`, `performance_acceptance_gate_passed`, `hardware_acceptance_eligible`은 각각 명확한 새 필드의 compatibility alias로 표시됩니다. 합성 상태와 같은 선행 상태가 없는 experimental input에서도 `paired_subtract`는 반복 blank 불확실성을 모델링하지 않으므로 `diagnostic_only_blank_uncertainty_unmodelled`로 보고되며 gate를 통과할 수 없습니다. 예전 `--confirm-power-analysis`은 제거되었고 `--locked-protocol-json`이 필요합니다. `--confirm-prespecified-gate`는 chronology self-attestation으로 남아 있으며 fingerprint가 이 시점을 증명하지는 못합니다. 보고서는 `power_analysis_calculations_machine_verified=true`와 별개로 `power_analysis_inputs_validated_by_this_tool=false`, `power_analysis_input_values_authenticated=false`를 유지합니다. 실험 증거를 만들려면 최소한 다음이 필요합니다.

Every number in [`deposition_trial_template.csv`](../examples/deposition_trial_template.csv) is synthetic — a demonstration-only example with `data_provenance=synthetic`. The analyzer reports `status=demonstration_only`, `dataset_rule_passed=false`, and `device_performance_validated=false` regardless of the numeric effect. The legacy `passed`, `analysis_pipeline_validated`, `performance_acceptance_gate_passed`, and `hardware_acceptance_eligible` fields are each shown as compatibility aliases for a clearer new field. Even for `experimental` input that carries no prior synthetic-like status, `paired_subtract` does not model repeated-blank uncertainty, so it is reported as `diagnostic_only_blank_uncertainty_unmodelled` and cannot pass the gate. The legacy `--confirm-power-analysis` flag has been removed and `--locked-protocol-json` is now required. `--confirm-prespecified-gate` remains a chronology self-attestation, and the fingerprint does not prove that point in time. The report keeps `power_analysis_inputs_validated_by_this_tool=false` and `power_analysis_input_values_authenticated=false` separate from `power_analysis_calculations_machine_verified=true`. Producing experimental evidence requires at least the following.

현재 acceptance planner는 `blank_policy=none`만 지원하고 실제 percentile-bootstrap gate operating characteristics도 검증하지 않았습니다. 따라서 향후 experimental input의 `passed=true`도 dataset-rule pass일 뿐 hardware-validation pass가 아니며 `device_performance_validated=false`가 유지됩니다.

The current acceptance planner supports only `blank_policy=none` and has not validated the actual percentile-bootstrap gate's operating characteristics. Consequently, even a future `experimental` input's `passed=true` is only a dataset-rule pass, not a hardware-validation pass, and `device_performance_validated=false` is retained.

1. 데이터를 보기 전에 primary endpoint, 최소 저감률, 제외, blank policy와 순서효과 분석을 프로토콜로 고정합니다.
   *Lock the primary endpoint, minimum reduction rate, exclusions, blank policy, and order-effect analysis into a protocol before viewing the data.*
2. pilot variance와 필요 power로 표본 수를 계획하고, 단순 CSV 행이 아닌 독립 day/aerosol run을 실험 단위로 삼습니다. device별 결과를 분리하고, 여러 device 일반화에는 별도 모델을 사용합니다.
   *Plan the sample size from pilot variance and the required power, using independent day/aerosol runs — not raw CSV rows — as the experimental unit. Keep per-device results separate and use a distinct model for generalizing across devices.*
3. ON/OFF 순서를 blocked randomization하고 양쪽 order의 최소 표본과 order별 효과 일관성을 확인합니다.
   *Block-randomize the ON/OFF order and confirm the minimum sample size for both orders and per-order effect consistency.*
4. blank를 반복 측정하고 신호와 동일한 면적·노출 기준으로 정규화하며, blank 측정 불확실성을 CI에 전파합니다.
   *Measure blanks repeatedly, normalize them to the same area/exposure basis as the signal, and propagate blank-measurement uncertainty into the CI.*
5. raw data, 무작위 스케줄, 일탈, calibration과 실행 환경의 provenance를 보존합니다.
   *Preserve the raw data, randomization schedule, deviations, calibration, and provenance of the execution environment.*

## 허용되는 표현 / Permitted phrasing

- "256채널 상대 위상 지연 계산이 이 장비에서 측정된 p99 시간 내 완료됐다." / "The 256-channel relative phase-delay calculation completed within the p99 time measured on this machine."
- "실측값이 아닌 기본 합성 noise 가정에서 p95 최악 채널 상대 위상 오차가 약 0.406°였다." / "Under the default synthetic-noise assumption (not a measured value), the p95 worst-channel relative phase error was about 0.406°."
- "정해진 pressure의 이상적인 1차원 정상파 모델에서 입자 크기별 potential을 계산했다." / "We computed the per-particle-size potential in an ideal 1-D standing-wave model at a stated pressure."
- "C 참조 구현이 테스트 호스트에서 Python 결과와 수치적으로 일치했다." / "The C reference implementation numerically matched the Python results on the test host."
- "합성 침착 template로 CSV와 분석 파이프라인을 실행했다." / "We ran the CSV and analysis pipeline against a synthetic deposition template."
- "외부 공진 채널 연구는 약 150 nm까지 기체 입자 조작 가능성을 보였다." / "An external resonant-channel study showed gas-particle manipulation feasibility down to about 150 nm."
- "Aegis 장치의 침착 저감률은 아직 측정되지 않았다." / "The Aegis device's deposition-reduction rate has not yet been measured."

다음 표현은 하드웨어 게이트 전에는 사용하지 않습니다. / The following phrasing is not used before the hardware gates are passed.

- "10–50 nm 파티클을 완전히 차단한다." / "Fully excludes 10-50 nm particles."
- "합성 noise 민감도 통과로 실제 256채널 정확도가 검증됐다." / "Passing the synthetic-noise sensitivity check validated real 256-channel accuracy."
- "69.444 ns tick만 맞추면 전체 1° 오차를 보장한다." / "Meeting the 69.444 ns tick alone guarantees the full 1° error budget."
- "합성 침착 template의 effect나 CI가 Aegis 저감률을 증명한다." / "The synthetic deposition template's effect or CI proves the Aegis reduction rate."
- "C parity 테스트가 driver 또는 HIL을 검증했다." / "The C parity test validated the driver or HIL."
- "가스 종류와 무관하게 같은 성능을 낸다." / "Delivers the same performance regardless of gas type."
- "완벽한 무마찰 wafer 이송을 제공한다." / "Provides perfectly frictionless wafer transport."
- "HVAC를 대체해 30% 이상 절감한다." / "Replaces HVAC for a 30%+ saving."

## 최소 벤치 프로토콜 / Minimum bench protocol

1. **장치 / Apparatus:** 실제 배열, 반사체, 기준 마이크, 온도·압력·습도 센서와 밀폐 시험 챔버를 사용합니다. / *Use a real array, reflector, reference microphone, temperature/pressure/humidity sensors, and a sealed test chamber.*
2. **조건 / Conditions:** Air/N2, 여러 유량과 50/100/150/300 nm의 전하 관리된 표준 aerosol을 사용합니다. / *Use Air/N2, multiple flow rates, and charge-controlled standard aerosols at 50/100/150/300 nm.*
3. **대조 / Controls:** 음장 ON/OFF를 blocked randomization하고 순서별 효과와 carryover를 보고합니다. / *Block-randomize the acoustic field ON/OFF and report per-order effects and carryover.*
4. **측정 / Measurement:** SMPS/CPC의 공간 분포와 300 mm witness wafer의 표면 침착 맵을 함께 기록합니다. / *Record SMPS/CPC spatial distribution together with a surface-deposition map on a 300 mm witness wafer.*
5. **부작용 / Side effects:** 재비산·다른 위치 재침착, 발열, wafer 진동, transducer particle adders, 초음파 누설을 측정합니다. / *Measure re-entrainment/redeposition elsewhere, heating, wafer vibration, transducer particle adders, and ultrasonic leakage.*
6. **통계 계획 / Statistical plan:** pilot variance에 기반한 power, 독립 day/device/aerosol run 수, 반복 blank와 불확실성 전파를 사전 정의합니다. / *Pre-specify power based on pilot variance, the number of independent day/device/aerosol runs, repeated blanks, and uncertainty propagation.*
7. **판정 / Acceptance:** 시험 전에 OEM과 목표 저감률·신뢰구간·허용 부작용·중단 기준을 합의합니다. / *Agree the target reduction rate, confidence interval, acceptable side effects, and stopping rules with the OEM before testing.*

입자 저감과 위상 보정이 각각 통과한 뒤에만 통합 시험을 수행합니다. 웨이퍼 부양은 별도 near-field 프로젝트로 유지합니다.

Combined testing is performed only after particle reduction and phase calibration each pass individually. Wafer levitation is kept as a separate near-field project.

## 외부 근거 / External references

- NIST/SEMATECH, [Paired Observations](https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm): paired 차이를 먼저 만들고 그 차이를 분석하는 실험 단위 해석의 기준 — *the standard for forming paired differences first and analyzing them as the experimental unit.*
- NIST/SEMATECH, [Sample Sizes Required](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm): 알려진 표준편차를 가정한 정규 평균 검정의 표본수 근사 기준. 본 planner는 이를 order별 보수적 screening에만 사용하며 bootstrap gate의 정확한 power로 간주하지 않음 — *the sample-size approximation for a normal-mean test with a known SD; this planner uses it only as a conservative per-order screen, not as the exact power of the bootstrap gate.*
- H. Bruus, "Acoustofluidics 7: The acoustic radiation force on small particles," *Lab on a Chip* 12, 1014-1021 (2012), DOI: [10.1039/C2LC21068A](https://doi.org/10.1039/C2LC21068A)
- R. J. Imani and E. Robert, "Estimation of acoustic forces on submicron aerosol particles in a standing wave field," *Aerosol Science and Technology* 52, 57-68 (2018), DOI: [10.1080/02786826.2017.1383968](https://doi.org/10.1080/02786826.2017.1383968)
