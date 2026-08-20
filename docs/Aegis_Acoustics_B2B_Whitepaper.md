# Aegis-Acoustics: 사전 하드웨어 타당성·한계 백서

**반도체 대기압 인터페이스용 국소 음장 제어 연구**
문서 상태: 연구 초안 · 증거 기준일 2026-08-21 · 문서 ID `AEGIS-FEASIBILITY-LIMITS-2026-08-21-R1`

*Pre-Hardware Feasibility & Limits Whitepaper — Localized acoustic-field control research for atmospheric-pressure semiconductor interfaces. Document status: research draft · evidence as of 2026-08-21 · document ID `AEGIS-FEASIBILITY-LIMITS-2026-08-21-R1`.*

> **문서 상태: 제품·하드웨어 성능 미검증 — 제품 및 고객 적용 NO-GO**
>
> 이 저장소가 확인한 것은 계산 코드, 합성 입력 민감도와 분석 절차입니다. 저장소에 포함된 **Aegis 하드웨어의 전기 위상, 3D 음장, 입자 침착 저감 및 안전성 실측 데이터는 0건**입니다. 현재 허용되는 다음 단계는 축소 벤치 실험을 설계하고 수행하는 것뿐입니다.
>
> 이 문서는 고객 성능 약속, 제품 사양, 구매·투자, fab 통합, 안전·규제 적합성 또는 생산 적용 판단의 근거로 사용할 수 없습니다. 특히 10–50 nm 차단, HVAC 대체, 웨이퍼 이송, 에너지 절감, 수율 또는 ROI를 입증하지 않습니다.
>
> **Document status: product/hardware performance UNVERIFIED — product and customer application is NO-GO.**
>
> What this repository has confirmed is calculation code, synthetic-input sensitivity, and analysis procedures. The repository contains **zero measured Aegis-hardware data** for electrical phase, the 3D acoustic field, particle-deposition reduction, or safety. The only next step currently permitted is designing and running a reduced-scale bench experiment.
>
> This document cannot be used as a basis for customer performance commitments, product specifications, procurement/investment, fab integration, safety/regulatory compliance, or production-deployment decisions. In particular, it does not demonstrate 10-50 nm exclusion, HVAC replacement, wafer transport, energy savings, yield, or ROI.

이 Markdown 파일이 현재 권위 문서입니다. PDF는 반드시 이 문서와 같은 revision에서 생성된 것만 사용해야 합니다. release tag나 서명된 문서가 아니므로, 역사적 수치는 [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md)의 명령으로 다시 실행해 확인해야 합니다.

*This Markdown file is the current authoritative document. Only a PDF generated from the same revision as this document may be used. Because it is not a release tag or a signed document, historical figures must be reconfirmed by re-running the commands in [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md).*

## 1. 30초 판정 / 1. The 30-Second Verdict

| 질문 / Question | 현재 가진 증거 / Evidence we currently have | 현재 판정 / Current verdict |
|---|---|---|
| 알려진 좌표·ToF로 256채널 지연을 계산할 수 있는가?<br>Can 256-channel delays be computed from known coordinates and ToF? | 자동 테스트, 호스트 benchmark, Python/C 수치 비교<br>Automated tests, host benchmarks, Python/C numerical comparison | **코드 경로만 verified**<br>**Code path only, verified** |
| 실제 배열이 1° 이내 전기 위상과 목표 음압을 달성하는가?<br>Does a real array achieve electrical phase within 1° and the target sound pressure? | Aegis 측정 데이터 없음<br>No Aegis measurement data | **미검증**<br>**Unverified** |
| 음장이 300 nm 입자의 wafer 침착을 줄이는가?<br>Does the acoustic field reduce wafer deposition of 300 nm particles? | 합성 CSV와 분석기만 있음<br>Only a synthetic CSV and an analyzer exist | **미검증; 벤치 실험 진행만 허용**<br>**Unverified; only proceeding to a bench experiment is permitted** |
| 150 nm까지 효과가 있는가?<br>Is it effective down to 150 nm? | 다른 폐쇄형 공진 장치의 외부 문헌만 있음<br>Only external literature from a different closed resonant device | **Aegis로 미검증**<br>**Unverified on Aegis** |
| 10–50 nm를 차단하는가?<br>Does it exclude 10-50 nm? | 현재 기준 모델이 적용성 검사를 통과하지 못하고 실측도 없음<br>The current reference model fails the applicability check and there is no measurement | **NO-GO** |
| HVAC를 대체하거나 에너지·수율·ROI를 개선하는가?<br>Does it replace HVAC or improve energy/yield/ROI? | 시스템 경계와 fab 데이터 없음<br>No system boundary or fab data | **NO-GO** |
| 안전·규제·cleanroom/OEM 적합성이 확인됐는가?<br>Has safety/regulatory/cleanroom/OEM compliance been confirmed? | 위험 분석과 적합성 시험 없음<br>No risk analysis or compliance testing | **미평가; 주장 금지**<br>**Unassessed; claims prohibited** |
| 비접촉 wafer 이송이 가능한가?<br>Is non-contact wafer transport possible? | 모델, 장치, 데이터 없음<br>No model, device, or data | **NO-GO** |

여기서 "벤치 실험 진행 허용"은 제품 또는 물리 실현가능성에 대한 GO가 아닙니다. 하드웨어 증거를 만들기 위한 제한된 다음 작업을 허용한다는 뜻만 가집니다.

*Here, "proceeding to a bench experiment is permitted" is not a GO on the product or on physical feasibility. It means only that a limited next step toward producing hardware evidence is permitted.*

## 2. 증거·판정 용어 / 2. Evidence and Verdict Terminology

이 문서의 수치는 다음 꼬리표 없이 인용하면 안 됩니다.

*Figures in this document must not be quoted without one of the following tags.*

| 꼬리표 / Tag | 의미 / Meaning | 의미하지 않는 것 / What it does not mean |
|---|---|---|
| **[코드] / [Code]** | 현재 저장소의 계산·schema·오류 처리가 테스트를 통과함<br>The current repository's calculation, schema, or error handling passes tests | 물리 정확도, 장치 성능, 현장 이식성<br>Physical accuracy, device performance, field portability |
| **[합성] / [Synthetic]** | 사람이 정한 분포·noise·예제 데이터를 넣은 계산 결과<br>A calculation result using human-chosen distributions, noise, or example data | 측정값, 제품 사양, 달성 확률<br>A measured value, product specification, or achievement probability |
| **[외부] / [External]** | 다른 연구팀·형상·조건에서 보고된 결과<br>A result reported by a different research team, geometry, or condition | Aegis 재현, wafer 침착 저감, 고객 환경 전이<br>Reproduction on Aegis, wafer deposition reduction, or transfer to a customer environment |
| **[미측정] / [Unmeasured]** | 필요한 Aegis 하드웨어 데이터가 없음<br>The needed Aegis hardware data does not exist | 0의 효과 또는 성공 가능성<br>Zero effect or zero probability of success |
| **[모델 범위 밖] / [Outside model scope]** | 현재 방정식의 적용성 검사를 통과하지 못함<br>Fails the current equation's applicability check | 최소 제어 크기, 정량 예측 또는 설계 상한<br>A minimum controllable size, a quantitative prediction, or a design ceiling |

보고서 필드와 문서 용어는 다음처럼 제한해서 해석합니다.

*Report fields and document terminology are interpreted with the following restrictions.*

- `verified`: 저장소 코드가 현재 테스트 환경에서 명시한 계산 또는 schema를 재현했다는 뜻만 가집니다.
  *`verified` means only that the repository code reproduced the stated calculation or schema in the current test environment.*
- `passed=true`: 하나의 잠긴 입력 데이터셋이 구현된 통계 규칙을 만족했다는 뜻만 가집니다. 제품 합격, 물리 재현성 또는 일반 성능을 뜻하지 않습니다.
  *`passed=true` means only that one locked input dataset satisfied an implemented statistical rule. It does not mean product acceptance, physical reproducibility, or general performance.*
- `validated`: 추적 가능한 Aegis 하드웨어와 독립 실험 데이터가 있는 경우에만 사용합니다. 현재 어떤 하드웨어 subsystem도 이 의미로 validated 상태가 아닙니다.
  *`validated` is used only when traceable Aegis hardware and independent experimental data exist. No hardware subsystem is currently `validated` in this sense.*
- `experimental`: 사용자가 CSV에 넣는 비인증 provenance label입니다. 도구가 실제 장치, 실험 수행 또는 원자료 진실성을 확인했다는 뜻이 아닙니다.
  *`experimental` is an unauthenticated provenance label the user puts in a CSV. It does not mean the tool verified the real device, the experiment's execution, or the truthfulness of the raw data.*
- `NO-GO`: 현재 증거로 그 주장이나 적용을 승인하지 않는다는 뜻입니다. 모든 미래 구현의 물리적 불가능성을 증명한다는 뜻은 아닙니다.
  *`NO-GO` means the current evidence does not approve the claim or application. It does not mean the claim is proven physically impossible for every future implementation.*
- `device_performance_validated=false`, `hardware_performance_validated=false`, `actual_bootstrap_gate_validated=false`는 현재 증거 경계를 직접 나타내는 필드입니다.
  *`device_performance_validated=false`, `hardware_performance_validated=false`, and `actual_bootstrap_gate_validated=false` are fields that directly express the current evidence boundary.*

현재 acceptance planner는 `blank_policy=none`만 지원합니다. 반복 blank의 불확실성을 endpoint와 CI에 전파하지 못하므로, 향후 experimental 데이터가 `passed=true`를 반환하더라도 이는 **dataset-rule pass**일 뿐 **hardware-validation pass가 아닙니다**. 실제 percentile-bootstrap gate의 type-I error와 power도 아직 calibration되지 않았습니다.

*The current acceptance planner supports only `blank_policy=none`. Because it cannot propagate repeated-blank uncertainty into the endpoint and CI, even if future `experimental` data returns `passed=true`, this is only a **dataset-rule pass**, not a **hardware-validation pass**. The actual percentile-bootstrap gate's type-I error and power have also not yet been calibrated.*

## 3. 현재 금지되는 주장 / 3. Currently Prohibited Claims

다음 표현은 이 저장소의 증거로 사용할 수 없습니다.

*The following statements cannot be supported by this repository's evidence.*

1. "Aegis가 입자 또는 침착을 X% 줄였다." / "Aegis reduced particles or deposition by X%."
2. "Aegis가 10–50 nm 입자를 차단·제거·제어한다." / "Aegis excludes, removes, or controls 10-50 nm particles."
3. "256채널 배열이 0.406° 또는 1° 이내 위상 정확도와 목표 초점 음압을 달성했다." / "The 256-channel array achieved phase accuracy within 0.406° or 1° and the target focal sound pressure."
4. "Aegis는 안전·규제·ESD·EMC·cleanroom·fab·OEM 적합성을 획득했다." / "Aegis has obtained safety/regulatory/ESD/EMC/cleanroom/fab/OEM compliance."
5. "생산 준비가 됐거나 wafer를 비접촉 이송할 수 있다." / "It is production-ready or can transport wafers without contact."
6. "HVAC를 대체하거나 에너지, 수율, uptime 또는 ROI를 개선한다." / "It replaces HVAC or improves energy, yield, uptime, or ROI."
7. "외부의 약 150 nm 조작 결과가 Aegis 성능을 입증한다." / "The external ~150 nm manipulation result proves Aegis performance."
8. "order당 23회면 실험 성공 또는 80% power가 보장된다." / "23 runs per order guarantees experimental success or 80% power."

현재 허용되는 표현은 다음 범위입니다.

*The currently permitted scope of statements is as follows.*

> "명시된 가정 아래 계산·분석 코드와 입력 검사를 재현했다. Aegis 하드웨어 성능은 아직 검증하지 않았다."
>
> "Under the stated assumptions, we reproduced the calculation/analysis code and input checks. Aegis hardware performance has not yet been validated."

## 4. 핵심 수치를 읽는 법 / 4. How to Read the Key Numbers

| 수치 / Number | 증거 등급과 실제 의미 / Evidence grade and actual meaning | 이 수치로 말할 수 없는 것 / What this number cannot say |
|---|---|---|
| `0.406°` | **[합성]** 독립 zero-mean Gaussian noise를 가정한 2,000회 계산에서 시행별 256채널 최악 상대 위상 오차의 경험적 p95<br>**[Synthetic]** The empirical p95 of the per-trial 256-channel worst-case relative phase error, over 2,000 calculations assuming independent zero-mean Gaussian noise | 하드웨어 정확도, 합격 확률, 신뢰구간 또는 제품 사양<br>Hardware accuracy, a pass probability, a confidence interval, or a product specification |
| `69.444 ns` | **[코드/설계 상한]** 40 kHz의 1° 예산 전체를 delay quantization 하나에만 배정하고 다른 오차를 0으로 둔 단일항 상한<br>**[Code / design ceiling]** A single-term ceiling that allocates the entire 1° budget at 40 kHz to delay quantization alone, with every other error set to zero | 구현된 clock 사양, 달성값 또는 전체 1° 보장<br>An implemented clock spec, an achieved value, or a guarantee of the full 1° budget |
| `124.8 nm` | **[모델 범위 밖]** 이상적 1-D 장, source peak 3 kPa, 3 cm, 293.15 K와 임의의 `10 kBT` 기준이 만나는 수학적 지름<br>**[Outside model scope]** The mathematical diameter where an ideal 1-D field, a 3 kPa source peak, 3 cm, 293.15 K, and an arbitrarily chosen `10 kBT` criterion happen to intersect | 최소 제어 크기, 차단 한계, 설계 목표, 낙관적 상한 또는 실험 예측<br>A minimum controllable size, an exclusion limit, a design target, an optimistic ceiling, or an experimental prediction |
| `약 150 nm` / `approx. 150 nm` | **[외부]** 50–80 kHz 폐쇄형 직사각형 flow-through 정상파 공진 채널에서 보고된 입자 조작 결과<br>**[External]** A particle-manipulation result reported in a 50-80 kHz closed rectangular flow-through standing-wave resonant channel | 차단·제거·wafer 침착 저감 또는 Aegis 배열 성능<br>Exclusion, removal, wafer deposition reduction, or Aegis array performance |
| `23 + 23 runs` | **[계획 surrogate]** 미검증 가정인 최소 저감 30%, 예상 저감 45%, log-ratio SD 0.35와 독립 run을 사용한 예시 표본수<br>**[Planning surrogate]** An example sample size using unverified assumptions — a minimum reduction of 30%, an assumed reduction of 45%, a log-ratio SD of 0.35 — and independent runs | 충분한 최소 표본, 실험 성공률 또는 실제 bootstrap power 보장<br>A sufficient minimum sample, an experimental success rate, or a guarantee of actual bootstrap power |
| `약 0.83` / `approx. 0.83` | **[합성/통계 surrogate]** 알려진 SD를 둔 z-surrogate의 독립 Monte Carlo 재계산 추정치; exact receipt는 증거 문서에 기록<br>**[Synthetic / statistical surrogate]** An independent Monte Carlo recomputation estimate of a known-SD z-surrogate; the exact receipt is recorded in the evidence document | 물리 SD, 실제 bootstrap gate, run 독립성, 결측·일탈, 다중 endpoint의 불확실성<br>The physical SD, the actual bootstrap gate, run independence, missingness/deviations, or multi-endpoint uncertainty |

`0.406°`, `124.8 nm`, `23 + 23`처럼 눈에 띄는 숫자를 꼬리표와 제한 문장 없이 분리해 재사용하면 문서 의미가 바뀝니다.

*Reusing an eye-catching number such as `0.406°`, `124.8 nm`, or `23 + 23` in isolation, without its tag and limitation sentence, changes the meaning of this document.*

## 5. 기술 트랙별 현재 상태 / 5. Current Status by Technical Track

### 5.1 국소 입자 제어 / 5.1 Localized Particle Control

**현재 가진 것 — [코드/외부] / What we have — [Code / External]**

- 정해진 peak pressure와 이상적인 1-D 정상파의 최적 위치를 가정해 입자 크기별 acoustic potential을 비교하는 [`기준 코드`](../simulation/aegis_radiation_force_feasibility.py)가 있습니다.
  *We have [reference code](../simulation/aegis_radiation_force_feasibility.py) that compares the acoustic potential by particle size, assuming a stated peak pressure and the optimal position of an ideal 1-D standing wave.*
- Imani와 Robert는 다른 폐쇄형 공진 채널에서 submicron aerosol을 측정하고 약 150 nm까지의 조작 가능성을 보고했습니다([2015](https://doi.org/10.1016/j.ultras.2015.06.021), [2018](https://doi.org/10.1080/02786826.2017.1383968)). 모델 선택 근거는 [`MODEL_SELECTION.md`](MODEL_SELECTION.md)에 있습니다.
  *Imani and Robert measured submicron aerosol in a different closed resonant channel and reported manipulation feasibility down to about 150 nm ([2015](https://doi.org/10.1016/j.ultras.2015.06.021), [2018](https://doi.org/10.1080/02786826.2017.1383968)). The model-selection rationale is in [`MODEL_SELECTION.md`](MODEL_SELECTION.md).*

**증명하지 않은 것 — [미측정/모델 범위 밖] / What this does not prove — [Unmeasured / Outside model scope]**

- 기본 10–300 nm 사례는 particle Knudsen number와 thermoviscous boundary-layer 적용성 검사를 통과하지 못합니다. 따라서 Gor'kov 결과는 이 크기 범위의 정량 예측이 아닙니다.
  *The default 10-300 nm case fails the particle Knudsen number and thermoviscous boundary-layer applicability checks. The Gor'kov result is therefore not a quantitative prediction in this size range.*
- 이상적인 1-D 계산은 장치 예측도, 물리적 상한도 아닙니다. 배열 형상, 반사체, 사이드로브, molecular/thermoviscous 효과, aerosol drag/slip, Brownian diffusion, streaming, 유량, surface deposition을 함께 풀지 않습니다.
  *The ideal 1-D calculation is neither a device prediction nor a physical ceiling. It does not jointly solve for array geometry, reflectors, sidelobes, molecular/thermoviscous effects, aerosol drag/slip, Brownian diffusion, streaming, flow rate, or surface deposition.*
- 입력한 source peak 3 kPa 자체도 Aegis 하드웨어가 달성·유지하거나 안전하게 운전할 수 있다고 측정된 값이 아닙니다.
  *The input source peak of 3 kPa is itself not a value measured to be achievable, sustainable, or safely operable by Aegis hardware.*
- 외부의 "조작"은 차단, 제거 또는 wafer 침착 저감을 뜻하지 않으며 Aegis에 이전할 수 없습니다.
  *The external "manipulation" does not mean exclusion, removal, or wafer deposition reduction, and it cannot be transferred to Aegis.*

**다음 gate / Next gate**

성공 보장이 아닌 실험 순서 후보는 먼저 300 nm에서 field ON/OFF 침착을 측정하고, 사전 gate를 통과한 뒤에만 150 nm를 검토하는 것입니다. 50/100 nm는 필요할 경우 메커니즘 탐색용으로만 측정하며 차단 목표나 합격 약속으로 사용하지 않습니다.

*A candidate experimental order — not a guarantee of success — is to first measure field ON/OFF deposition at 300 nm, and consider 150 nm only after passing the pre-specified gate. 50/100 nm, if needed, is measured only for mechanism exploration, not used as an exclusion target or an acceptance promise.*

### 5.2 환경 적응형 위상 계산과 측정 분석 / 5.2 Environment-Adaptive Phase Calculation and Measurement Analysis

**현재 가진 것 — [코드/합성] / What we have — [Code / Synthetic]**

- 알려진 경로 길이의 ToF에서 공통 timing offset과 평균 음속을 회귀하고, 좌표와 음속으로 direct-path 상대 지연을 계산합니다.
  *We regress a common timing offset and average sound speed from ToF at known path lengths, and compute direct-path relative delay from coordinates and sound speed.*
- 자동 테스트는 [`위상 계산 참조`](../simulation/aegis_phase_calibration.py)의 기하학적 일관성과 호스트 실행시간을 확인합니다.
  *Automated tests check the geometric consistency and host runtime of the [phase-calculation reference](../simulation/aegis_phase_calibration.py).*
- [`합성 불확실성 도구`](../simulation/aegis_phase_uncertainty.py)는 사람이 정한 noise 가정의 민감도만 계산합니다.
  *The [synthetic uncertainty tool](../simulation/aegis_phase_uncertainty.py) computes only the sensitivity to human-chosen noise assumptions.*
- 향후 256채널 전기 출력 측정 데이터를 처리하기 위한 [`분석기`](../analysis/aegis_phase_measurement_analysis.py)는 `measurement_plane=electrical_drive_output`, 공통 phase reference, 계측기·교정 기록 ID와 `cos_omega_t_plus_phi` 규약을 요구합니다. 공개 [`template`](../examples/phase_measurement_template.csv)은 합성입니다.
  *The [analyzer](../analysis/aegis_phase_measurement_analysis.py) built to process future 256-channel electrical-output measurement data requires `measurement_plane=electrical_drive_output`, a common phase reference, an instrument/calibration record ID, and the `cos_omega_t_plus_phi` convention. The published [template](../examples/phase_measurement_template.csv) is synthetic.*
- 합성 noise 민감도 결과가 `0.406°`이고, 독립 quantization 예산 계산이 `69.444 ns`입니다. 두 수치 모두 4절의 제한을 따릅니다.
  *The synthetic noise-sensitivity result is `0.406°`, and the independent quantization-budget calculation is `69.444 ns`. Both numbers are subject to the limits in Section 4.*

**증명하지 않은 것 — [미측정] / What this does not prove — [Unmeasured]**

- 현재 공개된 `experimental` 위상 CSV는 없습니다. 예제 256채널 CSV는 합성이며 수치가 좋아도 `passed=false`, `device_performance_validated=false`입니다.
  *No published `experimental` phase CSV currently exists. The example 256-channel CSV is synthetic, and even with good numbers it is `passed=false`, `device_performance_validated=false`.*
- 한 번의 공통 circular offset 적합은 절대 위상, target-microphone acoustic-arrival 위상, 채널 전달함수, 진폭, 초점 위치·음압, 사이드로브 또는 환경 구배를 검증하지 않습니다.
  *A single common circular-offset fit does not validate absolute phase, target-microphone acoustic-arrival phase, channel transfer functions, amplitude, focal position/pressure, sidelobes, or environmental gradients.*
- synthetic noise의 크기·분포·독립성은 센서, clock, driver 또는 배열에서 측정한 사양이 아닙니다.
  *The synthetic noise's magnitude, distribution, and independence are not specifications measured on a sensor, clock, driver, or array.*

**다음 gate / Next gate**

전기 구동 출력과 target acoustic-arrival을 서로 다른 측정 평면으로 분리해, 추적 가능한 계측기·교정 기록으로 256채널 전체를 측정해야 합니다. 그 뒤 3D pressure/phase field와 초점·사이드로브·drift를 독립적으로 확인합니다.

*The electrical drive output and the target acoustic arrival must be separated as distinct measurement planes, and all 256 channels must be measured with traceable instruments and calibration records. The 3D pressure/phase field and the focus/sidelobes/drift are then confirmed independently.*

### 5.3 침착 표본수 계획과 분석 / 5.3 Deposition Sample-Size Planning and Analysis

**현재 가진 것 — [코드/합성] / What we have — [Code / Synthetic]**

- [`planner`](../analysis/aegis_deposition_power.py)는 CSV row가 아니라 각 `independent_run_id`의 `mean(log(ON/OFF))`를 독립 endpoint로 사용합니다. 반복 측정은 독립 run 수를 늘리지 않습니다.
  *The [planner](../analysis/aegis_deposition_power.py) uses each `independent_run_id`'s `mean(log(ON/OFF))` — not the CSV row — as the independent endpoint. Repeated measurements do not increase the independent-run count.*
- 배포 예제는 300 nm, 가상 단일-device scope, Air, 10 slm, 600 s, 25 cm² 범위와 정확히 23 runs/order를 계산합니다. `example_only=true`, `execution_eligible=false`인 software-reproducibility fixture라서 acceptance 분석에 사용할 수 없습니다. 이 23이라는 값은 미검증 effect·SD·정규 surrogate 가정에 조건부입니다.
  *The shipped example computes exactly 23 runs/order for a 300 nm, hypothetical single-device scope, Air, 10 slm, 600 s, 25 cm² range. Because it is a software-reproducibility fixture with `example_only=true` and `execution_eligible=false`, it cannot be used for an acceptance analysis. The value 23 is conditional on unverified effect/SD/normal-surrogate assumptions.*
- 검색 stream과 별도 domain의 독립 surrogate 재계산 stream을 분리하고, 후자의 Wilson lower로 lock 가능 여부를 판정합니다. 이는 Monte Carlo 계산 오차만 다루며 실제 실험의 불확실성을 인증하지 않습니다.
  *The search stream is kept separate from an independent, separate-domain surrogate recomputation stream, and lock eligibility is judged on the latter's Wilson lower bound. This addresses only Monte Carlo computational error and does not certify the actual experiment's uncertainty.*
- 분석기는 장치·입자·가스·유량·노출·채집 면적·측정법·제외·중단·대체 정책, 분석 옵션과 정확한 총/order별 run 수를 잠긴 protocol에 결합합니다. bootstrap 반복은 10,000–1,000,000으로 제한합니다.
  *The analyzer binds device/particle/gas/flow-rate/exposure/collection-area/measurement-method/exclusion/stop/substitution policy, analysis options, and the exact total/per-order run count to a locked protocol. Bootstrap iterations are limited to 10,000-1,000,000.*

**증명하지 않은 것 — [미측정] / What this does not prove — [Unmeasured]**

- [`deposition_trial_template.csv`](../examples/deposition_trial_template.csv)는 전부 `data_provenance=synthetic`인 demonstration-only 데이터이며 [`분석기`](../analysis/aegis_deposition_analysis.py)는 효과 크기와 관계없이 `passed=false`, `device_performance_validated=false`를 보고합니다.
  *[`deposition_trial_template.csv`](../examples/deposition_trial_template.csv) is entirely demonstration-only data with `data_provenance=synthetic`, and the [analyzer](../analysis/aegis_deposition_analysis.py) reports `passed=false`, `device_performance_validated=false` regardless of effect size.*
- planner의 약 0.83은 known-SD z-surrogate 결과이고 실제 percentile-bootstrap gate의 type-I error/power가 아닙니다. 예제 SD 0.35도 Aegis pilot 측정값이 아닙니다.
  *The planner's ~0.83 is a known-SD z-surrogate result, not the actual percentile-bootstrap gate's type-I error/power. The example SD of 0.35 is also not an Aegis pilot-measured value.*
- acceptance planner는 `blank_policy=none`만 지원합니다. `paired_subtract`는 반복 blank 불확실성을 모델링하지 않아 diagnostic-only입니다.
  *The acceptance planner supports only `blank_policy=none`. `paired_subtract` does not model repeated-blank uncertainty and is diagnostic-only.*
- protocol SHA-256과 재계산은 파일 내용의 동일성과 내부 계산 일관성만 확인합니다. 원자료 무결성, 작성자·장치 identity, 작성·등록 시각, 실제 실행, 누락 run, 선택 보고, calibration, 정책 준수 또는 하드웨어 성능을 인증하지 않습니다.
  *The protocol SHA-256 and recomputation confirm only file-content identity and internal computational consistency. They do not certify raw-data integrity, author/device identity, time of writing/registration, actual execution, missing runs, selective reporting, calibration, policy compliance, or hardware performance.*
- day·batch 다양성은 진단용으로만 보고하며 그 효과를 추정하는 모델은 없습니다. 한 device의 결과를 다른 device, OEM 또는 fab으로 일반화할 수 없습니다.
  *Day/batch diversity is reported for diagnostics only, and there is no model estimating its effect. Results from one device cannot be generalized to another device, OEM, or fab.*

**다음 gate / Next gate**

실제 pilot의 독립 run SD에 사전 UCB/assurance를 적용하거나 보수 SD를 정당화해야 합니다. 외부 서명·timestamp가 있는 protocol, attempted-run ledger, deviation log, 반복 blank uncertainty model과 실제 analysis gate의 독립 type-I error/power calibration을 준비한 뒤 sample size를 다시 잠급니다.

*A pre-specified UCB/assurance must be applied to the real pilot's independent-run SD, or a conservative SD must be justified. The sample size is re-locked only after preparing an externally signed/timestamped protocol, an attempted-run ledger, a deviation log, a repeated-blank uncertainty model, and an independent type-I error/power calibration of the actual analysis gate.*

### 5.4 C 참조 코드 / 5.4 C Reference Code

**현재 가진 것 — [코드/호스트] / What we have — [Code / Host]**

[`sdk/aegis_core.c`](../sdk/aegis_core.c)와 [`sdk/aegis_core.h`](../sdk/aegis_core.h)는 ToF 회귀와 direct-path 상대 지연·위상 생성을 위한 stateless, allocation-free C 참조 코드입니다. 현재 호스트에서 Python 수치 비교, buffer/alias 계약과 C/C++ build를 테스트합니다.

*[`sdk/aegis_core.c`](../sdk/aegis_core.c) and [`sdk/aegis_core.h`](../sdk/aegis_core.h) are stateless, allocation-free C reference code for ToF regression and direct-path relative-delay/phase generation. On the current host, this is tested against Python numerical comparison, buffer/alias contracts, and C/C++ builds.*

**증명하지 않은 것 — [미측정] / What this does not prove — [Unmeasured]**

`sdk/`라는 경로명은 배포 가능한 장치 SDK 또는 firmware 준비도를 뜻하지 않습니다. 타겟 MCU/SoC, real-time deadline, sensor I/O, transducer driver, RTOS safety state, fault containment, HIL, 현장 ABI, MISRA 또는 안전 규격은 검증하지 않았습니다.

*The path name `sdk/` does not imply a distributable device SDK or firmware readiness. It has not validated a target MCU/SoC, real-time deadlines, sensor I/O, a transducer driver, RTOS safety state, fault containment, HIL, a field ABI, MISRA, or any safety standard.*

### 5.5 비접촉 wafer 이송 / 5.5 Non-Contact Wafer Transport

웨이퍼 부양은 국소 파티클 제어와 별도 연구 트랙입니다. 대형 평판에는 일반적으로 sub-mm gap의 near-field squeeze-film 접근이 필요하며 수 cm standoff 음장과 같은 문제로 취급할 수 없습니다. 현재 저장소에는 wafer 부양 모델, 장치 또는 데이터가 없으므로 생산 이송은 NO-GO입니다.

*Wafer levitation is a separate research track from localized particle control. Large flat panels generally require a sub-mm-gap near-field squeeze-film approach and cannot be treated as the same problem as a multi-centimeter-standoff acoustic field. The repository currently has no wafer-levitation model, device, or data, so production transport is NO-GO.*

## 6. 적용 범위와 명시적 제외 범위 / 6. Scope of Application and Explicit Exclusions

- 후보 연구 환경: 대기압 시험 챔버의 Air 또는 N2
  *Candidate research environment: Air or N2 in an atmospheric-pressure test chamber.*
- 첫 실험 후보: 300 nm 침착; 사전 gate 통과 후에만 150 nm 검토
  *First experimental candidate: 300 nm deposition; 150 nm is considered only after passing the pre-specified gate.*
- 별도 탐색 후보: 50/100 nm 메커니즘 측정. 차단 목표나 성능 약속이 아님
  *Separate exploratory candidate: 50/100 nm mechanism measurement. Not an exclusion target or a performance promise.*
- 제외/NO-GO: 진공 공정, 10–50 nm 완전 차단, 생산 wafer 부양, HVAC 대체
  *Excluded / NO-GO: vacuum processes, full 10-50 nm exclusion, production wafer levitation, HVAC replacement.*
- 결합 방식: 유동·포집·정전기와의 결합도 현재 미검증이며, 특히 정전기 방식은 별도 ESD/EMC·재료 적합성 평가가 필요함
  *Combination approaches: combining with flow control, capture, or electrostatics is also currently unverified, and an electrostatic approach in particular needs a separate ESD/EMC and materials-compatibility assessment.*

## 7. 미충족 하드웨어 증거 게이트 — 현재 0/8 완료 / 7. Unmet Hardware Evidence Gates — Currently 0/8 Complete

아래 여덟 gate는 모두 Aegis 하드웨어 증거를 요구합니다. 현재 저장소의 코드·합성 자료·외부 문헌만으로 완료 처리할 수 없습니다.

*All eight gates below require Aegis hardware evidence. They cannot be marked complete using only the current repository's code, synthetic material, and external literature.*

1. **Protocol과 추적성 / Protocol and traceability:** 외부 timestamp·서명이 있는 protocol, raw data, attempted-run ledger, deviation log, BOM·serial, firmware/config/commit, channel map과 환경 log를 보존합니다. / *Preserve an externally timestamped/signed protocol, raw data, an attempted-run ledger, a deviation log, BOM/serials, firmware/config/commit, a channel map, and environment logs.*
2. **계측 교정 / Instrument calibration:** microphone, phase, SMPS/CPC, flow, 온습도와 surface metrology의 교정 ID·불확실성·유효기간을 기록합니다. / *Record the calibration ID, uncertainty, and validity period for the microphone, phase, SMPS/CPC, flow, temperature/humidity, and surface-metrology instruments.*
3. **3D 음장 / 3D acoustic field:** Air/N2에서 pressure, phase, harmonic, streaming, 온도, sidelobe, drift와 fault map을 측정합니다. 입력 pressure의 달성·유지·안전성도 포함합니다. / *Measure pressure, phase, harmonics, streaming, temperature, sidelobes, drift, and a fault map in Air/N2, including whether the input pressure is achievable, sustainable, and safe.*
4. **전기와 음향 위상 / Electrical and acoustic phase:** electrical-drive output과 target acoustic-arrival을 분리하고 256채널 전체의 phase·amplitude·초점 위치를 측정합니다. / *Separate the electrical-drive output from the target acoustic-arrival and measure phase/amplitude/focal position across all 256 channels.*
5. **침착 대조시험 / Deposition controlled trial:** 먼저 300 nm에서 양 order의 blocked-randomized ON/OFF, 반복 blank, sham/negative control, 독립 day·batch·device를 사용하고 mass balance, 재비산, 다른 위치 재침착과 추가 particle 발생을 함께 평가합니다. / *Starting at 300 nm, use block-randomized ON/OFF across both orders, repeated blanks, sham/negative controls, and independent day/batch/device, while also assessing mass balance, re-entrainment, redeposition elsewhere, and additional particle generation.*
6. **통계 calibration / Statistical calibration:** pilot SD의 사전 불확실성 처리, blank uncertainty 전파, 실제 percentile-bootstrap gate의 독립 type-I error/power calibration과 결측·제외·중단 규칙을 잠급니다. / *Lock the pre-specified handling of pilot-SD uncertainty, blank-uncertainty propagation, an independent type-I error/power calibration of the actual percentile-bootstrap gate, and missing/exclusion/stopping rules.*
7. **안전·cleanroom 적합성 / Safety and cleanroom compliance:** operator와 service 위치의 가청음·초음파·고조파, ESD, EMC, 고전압·전기, 발열·화재, Air/N2·가스, 기계 고정, interlock·fault injection, outgassing, 재비산과 contamination adders를 시험합니다. / *Test audible/ultrasonic/harmonic exposure at operator and service positions, ESD, EMC, high-voltage/electrical, heat/fire, Air/N2/gas handling, mechanical fixturing, interlock/fault injection, outgassing, re-entrainment, and contamination adders.*
8. **재현성과 전이 / Reproducibility and transfer:** 복수 device·날짜·batch에서 재현하고, 새로운 OEM/fab·chamber·gas·flow 조건은 별도 검증합니다. / *Reproduce across multiple devices/dates/batches, and separately validate any new OEM/fab, chamber, gas, or flow condition.*

합격 기준은 OEM/fab 파트너와 결과를 보기 전에 정해야 하며 효과 크기와 신뢰구간을 함께 보고해야 합니다. 위 gate를 모두 통과하기 전에는 `validated`, "production-ready", "cleanroom-qualified" 또는 고객 성능 표현을 사용하지 않습니다.

*Acceptance criteria must be set with the OEM/fab partner before results are viewed, and effect sizes must be reported together with confidence intervals. Until every gate above is passed, the terms `validated`, "production-ready," "cleanroom-qualified," or any customer-performance phrasing are not used.*

## 8. 안전·규제 한계 / 8. Safety and Regulatory Limits

현재 프로젝트는 안전하거나 규제에 적합하다고 판정되지 않았습니다. 적용 규격은 장치 구조, 음압·주파수·고조파, 전압, 가스, 사용 지역, operator/service exposure와 OEM 요구를 기준으로 위험 분석 후 정해야 합니다.

*The project has not been determined to be safe or regulatorily compliant. Applicable standards must be determined after a risk analysis based on device construction, sound pressure/frequency/harmonics, voltage, gas, region of use, operator/service exposure, and OEM requirements.*

아직 평가하지 않은 범위에는 다음이 포함됩니다.

*Scope not yet assessed includes the following.*

- 사람의 가청·초음파 노출과 비선형 subharmonic/harmonic, service 위치 노출
  *Human audible/ultrasonic exposure and nonlinear subharmonic/harmonic content, exposure at service positions.*
- ESD·EMC, 고전압·누설전류, 전기 안전, 발열·화재
  *ESD/EMC, high voltage/leakage current, electrical safety, heat/fire.*
- N2 질식 및 가스 취급, 기계 고정·진동·파손
  *N2 asphyxiation and gas handling, mechanical fixturing/vibration/failure.*
- interlock, sensor/driver 고장, 통신 단절, fault injection과 fail-safe 상태
  *Interlocks, sensor/driver failure, communication loss, fault injection, and fail-safe states.*
- 재비산, 추가 particle 생성, 재료 outgassing, 세정제·process chemical compatibility와 cleanroom contamination budget
  *Re-entrainment, additional particle generation, material outgassing, cleaning-agent/process-chemical compatibility, and the cleanroom contamination budget.*

따라서 안전성, 규제 준수, cleanroom qualification, fab/OEM 승인 또는 현장 설치 가능성을 주장해서는 안 됩니다.

*Accordingly, claims of safety, regulatory compliance, cleanroom qualification, fab/OEM approval, or field-installability must not be made.*

## 9. 사업·통합 한계 / 9. Business and Integration Limits

국소 침착 저감이 재현되면 mini-environment 보조 모듈을 검토할 수 있지만, 한 chamber나 한 device의 결과는 다른 device, OEM 또는 fab으로 자동 전이되지 않습니다. HVAC는 열 제거, 습도, 압력차, 환기와 화학 오염 관리도 담당하므로 Aegis 단독 대체 대상이 아닙니다.

*If localized deposition reduction is reproduced, a mini-environment auxiliary module could be considered, but results from one chamber or one device do not automatically transfer to another device, OEM, or fab. HVAC also handles heat removal, humidity, pressure differential, ventilation, and chemical-contamination control, so it is not a candidate for standalone replacement by Aegis.*

현재 TRL 근거, BOM·원가, footprint, UPH 영향, 신뢰성, IP/FTO, retrofit fit, 기계·통신 인터페이스, EMC, process compatibility, 청소·유지보수, uptime, contamination budget, yield, 에너지 system boundary, CAPEX, OPEX 또는 ROI 데이터는 없습니다. 그러므로 양산 일정, 에너지 절감률, 수율 개선률과 경제성을 산정할 수 없습니다.

*There is currently no data on TRL basis, BOM/cost, footprint, UPH impact, reliability, IP/FTO, retrofit fit, mechanical/communication interfaces, EMC, process compatibility, cleaning/maintenance, uptime, contamination budget, yield, energy system boundary, CAPEX, OPEX, or ROI. Consequently, a production timeline, an energy-savings rate, a yield-improvement rate, and economics cannot be estimated.*

## 10. 현재 허용되는 다음 작업 / 10. Currently Permitted Next Steps

현재 판정은 **제품 NO-GO, 축소 벤치 검증 준비 GO**입니다. 허용되는 범위는 다음과 같습니다.

*The current verdict is **product NO-GO, GO only for preparing a reduced-scale bench validation**. The permitted scope is as follows.*

1. 300 nm용 외부 timestamp protocol과 안전 사전점검을 작성합니다. / *Write an externally timestamped protocol and a safety pre-check for 300 nm.*
2. calibration·traceability가 있는 단일 chamber 장치를 구성합니다. / *Build a single-chamber apparatus with calibration and traceability.*
3. 3D 음장과 전기/음향 위상을 먼저 측정합니다. / *Measure the 3D acoustic field and electrical/acoustic phase first.*
4. pilot으로 SD·blank·환경 변동을 추정하고 actual gate를 calibration합니다. / *Use a pilot to estimate SD/blank/environmental variation and calibrate the actual gate.*
5. 그 결과로 표본수와 acceptance criteria를 다시 잠근 뒤 confirmatory deposition trial을 수행합니다. / *Re-lock the sample size and acceptance criteria from those results, then run the confirmatory deposition trial.*

이 단계의 완료 여부는 [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md)에 증거 링크와 함께 기록합니다. 모델 변경은 [`MODEL_SELECTION.md`](MODEL_SELECTION.md)의 병합 gate를 따릅니다.

*Completion of these steps is recorded in [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md) together with evidence links. Model changes follow the merge gate in [`MODEL_SELECTION.md`](MODEL_SELECTION.md).*

---

*Aegis-Acoustics R&D Project © 2026. Research draft released under the repository MIT License.*
