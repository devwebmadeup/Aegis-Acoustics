# 🛡️ Aegis-Acoustics

**Open Research Platform for Local Acoustic Particle Control in Semiconductor Interfaces**

**반도체 인터페이스용 국소 음향 파티클 제어 오픈 연구 플랫폼**

> **현재 제품·고객 적용 판정: NO-GO.** 이 저장소에 포함된 Aegis 하드웨어의 전기 위상, 3D 음장, 입자 침착 저감 또는 안전성 실측 데이터는 **0건**입니다. 확인된 것은 코드·합성 입력·분석 절차뿐이며, 현재 허용되는 다음 단계는 축소 벤치 실험 준비입니다. 분석기의 `passed=true`도 dataset-rule pass일 뿐 hardware-validation pass가 아닙니다. 자세한 증거 경계와 금지 주장은 [사전 하드웨어 타당성·한계 백서](docs/Aegis_Acoustics_B2B_Whitepaper.md)를 먼저 읽으십시오.
>
> **Current product/customer-use verdict: NO-GO.** The repository contains no Aegis hardware measurements of electrical phase, 3D acoustic field, deposition reduction, or safety. Read the [hardware-prevalidation limitations whitepaper](docs/Aegis_Acoustics_B2B_Whitepaper.md) before using any number in this repository.

Aegis-Acoustics evaluates whether localized acoustic fields can supplement contamination control in atmospheric semiconductor interfaces such as EFEMs and FOUP test environments. It is not currently a replacement for cleanroom HVAC.
Aegis-Acoustics는 EFEM·FOUP 시험 환경 같은 대기압 반도체 인터페이스에서 국소 음장이 오염 제어를 보조할 수 있는지 평가합니다. 현재 단계에서는 클린룸 HVAC 대체 기술이 아닙니다.

The repository separates two questions: whether the calculation path maps supplied Time-of-Flight inputs to phased-array delays, and whether a bounded acoustic field measurably reduces deposition for a specified particle size and gas. Only the calculation path can be tested in software; live acquisition, closed-loop adaptation, and deposition require hardware experiments.
이 저장소는 주어진 ToF 입력을 위상 배열 지연으로 바꾸는 계산 경로와, 특정 입자 크기·가스 조건에서 음장이 실제 침착을 줄이는지를 분리합니다. 소프트웨어로 확인할 수 있는 것은 계산 경로뿐이며 live acquisition·폐루프 적응·침착 저감은 하드웨어 실험이 필요합니다.

## ⚠️ The Problem / 핵심 문제

Advanced fabs benefit from localized contamination control, but HVAC also provides heat removal, humidity and pressure control. Gas composition and temperature alter acoustic propagation, so an array calibrated in one environment cannot be assumed to retain the same focal field in another.

첨단 fab에는 국소 오염 제어의 가치가 있지만 HVAC는 열 제거, 습도 및 압력 제어도 담당합니다. 또한 가스 조성과 온도가 음향 전파를 바꾸므로 한 환경에서 보정한 배열이 다른 환경에서도 같은 초점장을 유지한다고 가정할 수 없습니다.

## 💡 Research Approach / 연구 접근

Instead of claiming room-scale replacement, Aegis tests localized control close to the wafer environment. The software reference evaluates **Adaptive Phase Calibration** as follows:

1. Collects Time-of-Flight (ToF) samples at known reference path lengths.
2. Fits `time = trigger_offset + distance / sound_speed`, separating a shared timing offset from path delay.
3. Recalculates relative phase delays for 256 transducers and benchmarks the computation against a 0.1s software target.

방 전체의 정화를 대체한다고 주장하는 대신, 웨이퍼 환경 가까이에서 국소 제어를 시험합니다. 소프트웨어 참조 구현은 **적응형 위상 보정(Adaptive Phase Calibration)**을 다음처럼 평가합니다:

1. 알려진 기준 경로 길이에서 Time of Flight(ToF) 샘플을 수집합니다.
2. `time = trigger_offset + distance / sound_speed`를 적합해 공통 timing offset과 경로 지연을 분리합니다.
3. 256개 트랜스듀서의 상대 위상 지연을 계산하고 0.1초 소프트웨어 목표와 비교해 벤치마크합니다.

Passing this benchmark proves only the computation path. Microphone accuracy, per-channel transfer functions, focal pressure recovery, and particle reduction remain hardware measurements.
이 벤치마크 통과는 계산 경로만 증명합니다. 마이크 정확도, 채널별 전달함수, 초점 음압 복구 및 파티클 저감은 별도의 하드웨어 측정 대상입니다.

The seeded phase-uncertainty command is also a software sensitivity study, not a measurement. With its default assumed independent Gaussian noise (100 ns timestamp and 50 µm reference distance), 2,000 synthetic trials produced a p95 trial-worst-channel relative phase error of approximately **0.406°**. The reported **69.444 ns** delay tick is a standalone upper bound obtained by allocating the entire 1° budget at 40 kHz to quantization; calibration, clock, driver, and channel errors must share that budget in hardware.

위상 불확실성 명령도 측정이 아닌 소프트웨어 민감도 분석입니다. 기본 가정인 서로 독립인 Gaussian noise(timestamp 100 ns, 기준 거리 50 µm)로 2,000회 합성 시행한 결과, 각 시행의 최악 채널 상대 위상 오차 p95는 약 **0.406°**였습니다. **69.444 ns** delay tick은 40 kHz에서 1° 예산 전체를 양자화에만 배정한 독립 상한이며, 실제 하드웨어에서는 보정·클럭·드라이버·채널 오차와 예산을 나눠야 합니다.

## 🔬 실현가능성 검증 (Feasibility Verification)

> 아래 판정은 소프트웨어 계산, 외부 실험 문헌, Aegis 하드웨어 실험을 구분합니다. 현재 저장소에는 Aegis 하드웨어 실험 데이터가 없습니다.
>
> The verdicts distinguish software checks, external experimental literature, and Aegis hardware evidence. This repository currently contains no Aegis hardware measurements.

**종합 판단 / Overall verdict: 제품 NO-GO, 축소 벤치 검증 준비만 진행 허용 (product NO-GO; scoped bench-validation preparation only)**

| 서브시스템 / Subsystem | 판정 / Verdict | 근거 (KR) | Rationale (EN) |
|---|---|---|---|
| 적응형 위상 계산<br>Adaptive Phase Computation | ✅ 코드 검증 가능<br>Software-verifiable | 알려진 배열 좌표·거리·ToF에서 평균 음속과 상대 지연을 계산하고 자동 테스트·벤치마크 가능. 실제 초점 복구는 미증명. | Geometry, mean speed of sound, and relative delays can be tested and benchmarked; focal recovery remains unproven. |
| 합성 위상 불확실성<br>Synthetic Phase Uncertainty | 🟡 민감도 분석<br>Sensitivity only | 기본 합성 noise에서 p95 최악 채널 오차는 약 0.406°. noise는 실측 스펙이 아니며 `hardware_accuracy_validated=false`. | The default assumed-noise run yields about 0.406°; its noise parameters are not hardware measurements and hardware accuracy remains false. |
| 향후 전기 출력 측정 데이터용 256채널 분석기<br>Drive-phase Measurement Pipeline | ✅ 분석 경로 검증<br>Pipeline only | 전기 구동 출력·공통 참조·cos 부호 규약을 명시한 256채널 CSV에서 전역 오프셋 제거 후 p95/max를 계산. 현재 template은 합성이며 실제 계측 데이터는 없음. | Processes future electrical-drive measurements under a strict schema. The template is synthetic; no measured Aegis run is included. |
| 이상적 정상파 추정<br>Ideal Standing-wave Estimate | ✅ 코드 검증 가능<br>Software-verifiable | 수정된 Gor'kov 계수와 potential barrier로 10/50/150/300nm를 비교. 10–300 nm 기본값에는 연속체 적용성 gap이 있으며 실제 3D 장치 예측이 아님. | Compares particle sizes using a corrected Gor'kov convention, but the default 10–300 nm regime has a continuum-applicability gap and is not a 3D device prediction. |
| 150nm급 기체 입자 조작<br>~150nm Gas-particle Manipulation | 🟡 외부 근거만<br>External evidence only | 50–80 kHz 직사각형 flow-through 정상파 공진 채널 실험은 존재하지만 Aegis open phased-array 형상·wafer 침착 저감 데이터는 없음. | External evidence comes from a 50–80 kHz rectangular flow-through standing-wave resonator/channel, not an Aegis open phased array or wafer-deposition trial. |
| 침착 표본수·protocol lock<br>Deposition Power/Protocol | ✅ 계획 계산 검증<br>Planning only | 독립 run log-ratio와 양 order 공동 통과를 기준으로 표본수를 계획하고 입력·계산결과를 SHA-256 lock으로 결합. known-SD z surrogate이며 실제 bootstrap power가 아님. | Plans independent runs for both orders and locks inputs/results by SHA-256. It is a known-SD z surrogate, not validated power for the actual bootstrap gate. |
| 침착 분석 파이프라인<br>Deposition-analysis Pipeline | ✅ 코드 경로 검증<br>Pipeline only | paired log-ratio·독립 run cluster bootstrap·order gate를 테스트. 실험 pass에는 재계산으로 검증된 locked power protocol이 필요하며, 합성 template은 항상 `passed=false`. | Tests paired statistics, independent-run resampling, and order gates. An experimental pass requires a recomputed locked power protocol; synthetic data never passes. |
| C 참조 구현<br>C Reference Implementation | ✅ 호스트 수치 일치<br>Host parity/ABI | stateless C 구현을 Python 참조와 비교하고 C/C++ ABI를 테스트. 센서·driver·HIL은 없음. | The stateless C calculations have Python parity and host ABI tests; sensor I/O, drivers, and HIL are absent. |
| 10–50nm 완전 차단<br>Complete 10–50nm Blocking | 🔴 NO-GO<br>Unsupported | 현재 3kPa 이상장 추정에서는 안정적 potential 장벽이 부족하고, 분자·열점성 영역 모델도 필요. | The current ideal-field estimate at 3 kPa lacks a robust potential barrier, and the regime also needs molecular/thermoviscous modeling. |
| 비접촉 웨이퍼 이송<br>Wafer Levitation Transport | 🔴 제품 적용 NO-GO<br>Separate research track only | 외부 near-field 실증은 있으나 sub-mm squeeze-film 장치이며 본 연구와 다른 구조. 현재 저장소에는 모델·장치·데이터가 없음. | External near-field demonstrations use a separate sub-mm squeeze-film architecture; this repository has no transport model, device, or data. |
| 진공 챔버 배제<br>Vacuum chamber exclusion (scope) | ✅ 타당<br>Sound | 소리가 진공에서 전파 불가하다는 물리적 한계를 정확히 인지하고 스코프에서 제외. | Correctly recognizes that sound cannot propagate in vacuum and scopes the system out of core (vacuum) process steps accordingly. |
| HVAC 대체·에너지 절감 수치<br>HVAC Replacement / Savings | 🔴 NO-GO | HVAC 기능을 대체한다는 하드웨어·에너지 감사 근거가 없음. | No hardware or energy-audit evidence supports HVAC replacement or a savings percentage. |

**결론 (KR):** 현재 코드로 증명할 수 있는 것은 위상 계산·호스트 실행시간·합성 noise 민감도·C/Python 수치 일치·향후 측정 데이터용 위상/침착 분석 파이프라인과, 명시된 가정 아래의 이상적 정상파 계산입니다. 이들은 장치 성능 증거가 아닙니다. 첫 하드웨어 실험 후보는 300 nm이며, 해당 gate 통과 후에만 150 nm를 검토합니다. 10–50 nm와 HVAC 대체는 NO-GO입니다.

**Conclusion (EN):** The code establishes calculation consistency, host runtime, assumed-noise sensitivity, C/Python numerical parity, measured-drive-phase/deposition pipeline behavior, and results under explicit ideal standing-wave assumptions. None is device-performance evidence. The first hardware target is deposition reduction from 300 nm down toward 150 nm; 10–50 nm blocking and HVAC replacement remain NO-GO.

증거 정의·재현 방법 / Evidence definitions and reproduction: [`docs/FEASIBILITY_EVIDENCE.md`](docs/FEASIBILITY_EVIDENCE.md). 나노입자 모델 선택과 연속체 gap: [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).

## 재현 가능한 출력 / Reproducible Outputs

**[모델 범위 밖 — 최소 제어 크기가 아님]** 기본 조건(공기, source peak 3 kPa, 3 cm, 293.15 K, 임의로 선택한 10 kBT 기준)의 이상장 계산은 40 kHz에서 수학적 교차 지름 **124.8 nm**를 반환합니다. 같은 조건에서 10/20/50/100/150/300 nm의 `DeltaU/kBT`는 각각 약 **0.005/0.041/0.643/5.14/17.4/139**입니다. 이 모든 나노 크기 사례가 현재 코드의 Knudsen·thermoviscous 유효성 검사를 통과하지 못하고 입력 3 kPa도 하드웨어 달성값이 아니므로, 이 숫자를 최소 제어 크기·차단 한계·설계 목표 또는 실험 예측으로 인용할 수 없습니다.

The default ideal-field calculation (air, 3 kPa source peak, 3 cm, 293.15 K, selected 10 kBT criterion) returns **124.8 nm** at 40 kHz. All listed nanoscale cases fail the current Knudsen/thermoviscous applicability checks, so these outputs are not device-performance predictions.

### Quickstart

```bash
python3 -m pip install -r requirements.txt
make verify
make phase-benchmark
make phase-uncertainty
make phase-measurement-example
make radiation-report
make deposition-power
make deposition-example
make whitepaper-check
```

`make verify`는 stateless C 참조 구현의 strict C/C++ 빌드와 전체 테스트를 실행합니다. `make whitepaper-check`는 PDF에 결합된 Markdown·renderer SHA-256과 문서 ID·NO-GO metadata를 확인해 구형 PDF 재배포를 차단합니다. 명령의 exit code 0, `verified=true` 또는 `--report-only` 성공은 코드 실행 성공일 뿐 장치 성능 pass가 아닙니다. `make phase-measurement-example`과 `make deposition-example`은 둘 다 synthetic template를 분석하는 `demonstration_only` 데모이며 성능 증거를 만들지 않습니다. 위상 분석 v2는 `electrical_drive_output` 계측만 받으며 target-microphone/acoustic-arrival 위상은 별도 전파 분석이 필요합니다.

`make deposition-power`는 **실행용이 아닌 software-reproducibility fixture**의 planning input에서 계산을 다시 실행해 fingerprint와 결과를 검증합니다. 300 nm 예제 가정(최소 저감 30%, 예상 저감 45%, log-ratio SD 0.35, joint target power 0.80)은 **order당 23회, 총 46회의 독립 run**을 계산합니다. 이 값은 실험 데이터·충분한 표본 보장·실제 percentile-bootstrap gate power가 아니며 SD 가정의 진실성이나 protocol 사전 등록 시점을 증명하지 않습니다. 실험 gate의 예전 `--confirm-power-analysis` self-attestation은 제거되었습니다. 이제 `--locked-protocol-json`이 분석 옵션과 CSV `protocol_id`뿐 아니라 장치·입자·가스·유량·노출·채집 면적·측정법·제외정책, 정확한 총/order별 run 수와 중단·대체 규칙에 일치해야 합니다.

새 실험 계획은 [`deposition_protocol_config.json`](examples/deposition_protocol_config.json)을 복사해 **결과를 보기 전에** `protocol.example_only=false`, 실제 protocol/device/rule ID, 범위와 가정을 모두 바꾼 뒤 plan→lock→verify 순서로 만듭니다. 배포 fixture는 `example_only=true`, `execution_eligible=false`라서 deposition acceptance 분석에 사용할 수 없습니다. `lock`은 기존 출력 파일을 덮어쓰지 않습니다.

```bash
plan_dir="$(mktemp -d)"
python3 analysis/aegis_deposition_power.py plan examples/deposition_protocol_config.json > "$plan_dir/planned.json"
python3 analysis/aegis_deposition_power.py lock "$plan_dir/planned.json" --output "$plan_dir/locked.json"
python3 analysis/aegis_deposition_power.py verify "$plan_dir/locked.json"
```

## 📁 Repository Contents / 리포지토리 구성

- [`/docs`](docs/README.md): The Markdown limitations whitepaper is authoritative; the PDF is a generated reading copy of that same document ID. The evidence matrix and model-selection record define reproduction and model boundaries. — Markdown 한계 백서가 권위 원문이며 PDF는 같은 문서 ID의 생성 사본입니다. 증거 매트릭스와 모델 선택 기록이 재현·모델 경계를 정의합니다.
- `/simulation`: Phase-calibration reference and bounded radiation-force analysis. `aegis_particle_sim.py` is explicitly a concept animation, not a digital twin. — 위상 보정 참조 구현과 제한된 방사력 분석. `aegis_particle_sim.py`는 디지털 트윈이 아닌 개념 애니메이션입니다.
- `/analysis` and `/examples`: Pipelines for future electrical-drive measurements, prospective deposition-power locking, paired-deposition analysis, and synthetic/example-only templates; none is Aegis performance data. — 향후 전기 구동 측정 데이터용 분석·사전 침착 power lock·paired 침착 분석과 synthetic/example-only template이며 Aegis 성능 데이터가 아닙니다.
- [`/sdk`](sdk/README.md): A stateless, allocation-free C reference implementation with Python numerical-parity and host ABI/build tests. It is not a sensor stack, transducer driver, safety controller, or HIL result. — stateless C 참조 구현과 Python 수치 일치·호스트 ABI 테스트를 제공하지만 driver·안전 제어기·HIL은 아닙니다.
- `/tools`: Fail-closed Markdown-to-PDF rendering and source-identity checks for the limitations whitepaper. — 한계 백서 PDF 생성과 source-identity 검사를 fail-closed 방식으로 수행합니다.

## 🤝 Call for Hardware Contributors / 하드웨어 기여자 모집

The repository now provides bounded analytical checks and a phase-calibration software reference. Hardware contributors are needed to build the pressure-field and particle-deposition evidence defined in the validation protocol.

If you are an embedded engineer, acoustic physicist, or hardware maker, grab the code, build the physical array, and let's fix this broken process together. PRs and discussions are heavily welcomed.

저장소는 제한된 분석 모델과 위상 보정 소프트웨어 참조를 제공합니다. 검증 프로토콜에 정의된 음장·파티클 침착 증거를 만들 하드웨어 기여자가 필요합니다.

임베디드 엔지니어, 음향 물리학자, 하드웨어 메이커라면 누구든 코드를 가져가 실제 배열을 만들어 함께 이 문제를 해결해 주시길 바랍니다. PR과 토론을 언제나 환영합니다.

## 📜 License / 라이선스

This project is licensed under the MIT License - see the LICENSE file for details.

이 프로젝트는 MIT 라이선스를 따릅니다 — 자세한 내용은 LICENSE 파일을 참고하세요.
