# 서브시스템별 실현가능성 추정 (초기) / Initial Feasibility Estimates by Subsystem

이 문서는 GitHub Issue #1의 내용을 저장소에 영구 기록한 것입니다. **아래 퍼센트는 물리학·산업 선례에 근거한 주관적 공학 판단(engineering judgment)이며, [`../FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md)의 증거 등급 체계(코드 검증/합성/외부/미측정)로 검증된 값이 아닙니다.** 이 문서는 조사의 *출발점*이며, 하이브리드 관련 추정치는 이후 [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md)의 정량 계산으로 갱신되었습니다 — 하이브리드 수치를 인용할 때는 반드시 그 문서의 최신 값을 사용하세요.

This document permanently records the content of GitHub Issue #1 in the repository. **The percentages below are subjective engineering judgment grounded in physics and industry precedent — they are not values validated under the evidence-grading system (code-verified/synthetic/external/unmeasured) in [`../FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md).** This document is the *starting point* of the investigation; the hybrid-related estimates were later updated by the quantitative calculation in [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md) — when citing hybrid numbers, always use that document's current values.

## 영역별 추정 (Issue #1 원문) / Estimates by area (as originally posted in Issue #1)

| 영역 / Area | 추정 / Estimate | 근거 / Reasoning |
|---|---|---|
| 256채널 위상 제어 (실물 하드웨어 <1°)<br>256-ch phase control on real hardware, <1° | **~90%** | 의료 초음파·소나·mid-air haptics에서 이미 상용화된 성숙 기술. 물리적 리스크가 아니라 엔지니어링/통합 리스크.<br>Mature, already commercialized elsewhere (medical ultrasound, sonar, mid-air haptics). Integration risk, not physics risk. |
| 비접촉 wafer 부양 (근접장 squeeze-film)<br>Non-contact levitation via near-field squeeze-film | **~55-65%** | 소형 패널에서 실증됐지만 300mm wafer로 스케일업하는 tilt/uniformity/drop 제어는 별도 과제.<br>Demonstrated for smaller panels; scaling to a full 300mm wafer's tilt/uniformity/drop control is a separate engineering task. |
| 10–50nm 입자를 순수 음향 방사력으로, 수 cm 거리에서 직접 차단 (백서의 문자 그대로의 주장)<br>Direct radiation-force exclusion of 10-50nm particles at cm-scale standoff (literal whitepaper claim) | **~3-5%** | 근본적 척도 장벽(Knudsen number 위반) — [`../MODEL_SELECTION.md`](../MODEL_SELECTION.md) 참고.<br>Fundamental scale barrier (Knudsen-number violation) — see [`../MODEL_SELECTION.md`](../MODEL_SELECTION.md). |
| 하이브리드 재설계 (음향 응집으로 유효 입자 크기를 키운 뒤 push, 또는 정전기 보조) — **초기 추정, 이후 개정됨**<br>Hybrid redesign (acoustic agglomeration to grow effective size, then push; or electrostatic assist) — **initial estimate, later revised** | ~~**~25-35%**~~ → [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md)에서 시나리오별로 세분화·개정됨 (~2-5%, ~15-20%, ~20-30%) | 산업적 선례는 있었으나, cleanroom의 극저 입자 농도(n² 문제)는 이 시점에는 아직 검토되지 않음.<br>Industrial precedent existed, but the cleanroom's extremely low particle concentration (the n² problem) had not yet been examined at this point. |
| 안전·규제 적합성 (핵심 하드웨어 작동 전제)<br>Safety/regulatory compliance (conditional on core hardware working) | **~85%** | 표준 EE/음향 노출 인증 프로세스, 새로운 물리 불필요.<br>Standard EE/acoustic-exposure certification; no new physics required. |
| HVAC 대체·30% 에너지 절감·ROI<br>HVAC replacement, 30% energy savings, ROI | **산정 불가 / Unscoreable** | 시스템 경계·fab 데이터 전무.<br>No system boundary or fab data exists at all. |

## 왜 10–50nm 직접 차단이 가장 낮은가 / Why direct sub-50nm exclusion scores lowest

`simulation/aegis_radiation_force_feasibility.py`의 `min_diameter_validity` 출력이 보여주는 Knudsen number 위반이 핵심입니다. 1기압 공기의 분자 평균자유행로는 약 66nm(`AIR_MEAN_FREE_PATH_M`)이고, 10-50nm 입자(반경 5-25nm)의 Kn은 약 2.6-13으로 연속체 음향 산란 이론이 성립하는 영역(Kn≪0.1)을 완전히 벗어납니다. 이 크기의 입자는 파동에 산란되는 연속체가 아니라 개별 기체 분자에 부딪히는 free-molecular 영역의 대상이며, 이는 모델 정교화로 풀리는 문제가 아니라 다른 물리 체제로의 전환입니다. [`../MODEL_SELECTION.md`](../MODEL_SELECTION.md)가 인용하는 외부 실증 하한(Imani & Robert, 약 150nm)도 Kn~1 문턱(공기 중 약 132nm)과 거의 일치합니다 — 우연이 아닐 가능성이 높습니다.

The key is the Knudsen-number violation shown in `min_diameter_validity` from `simulation/aegis_radiation_force_feasibility.py`. Air's molecular mean free path at 1 atm is about 66nm (`AIR_MEAN_FREE_PATH_M`), and the Knudsen number for 10-50nm particles (5-25nm radius) runs roughly 2.6-13 — well outside the regime where continuum acoustic-scattering theory (Kn≪0.1) applies. At this size a particle isn't a continuum body the wave scatters off; it's in the free-molecular regime, individually bombarded by gas molecules. That's a shift to a different physical regime, not something a refined model fixes incrementally. The external experimental floor cited in [`../MODEL_SELECTION.md`](../MODEL_SELECTION.md) (Imani & Robert, ~150nm) sits almost exactly at the Kn~1 threshold (~132nm in air) — likely not a coincidence.

## 왜 하이브리드가 처음엔 더 유망해 보였는가 / Why the hybrid path looked more promising initially

산업용 음향 응집(acoustic agglomeration)은 이미 배기가스 PM2.5/PM10 처리에 상용화되어 있습니다. 개별 초미세입자를 직접 밀어내는 대신, 음장이 입자 간 상대운동(orthokinetic collision)을 늘려 응집시키고 커진 입자를 그다음에 처리합니다. `simulation/aegis_radiation_force_feasibility.py`의 모델 수치상 방사력이 10 kBT 장벽을 넘기 시작하는 지점은 대략 125-165nm입니다 — 즉 "10-50nm를 직접 차단"이 아니라 "10-50nm를 150nm 이상으로 응집시킨 뒤 그 이상을 밀어낸다"는 재설계라면 현재 코드의 물리 범위 안에서 말이 되는 경로처럼 보였습니다. **이 초기 판단이 응집 자체의 농도 의존성을 검토하기 전에 나온 것이었고, [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md)에서 그 검토 결과 크게 하향 조정되었습니다.**

Industrial acoustic agglomeration is already commercialized for exhaust PM2.5/PM10 treatment. Instead of directly pushing individual ultrafine particles, the acoustic field increases orthokinetic collisions so particles clump together, and the larger clumps are handled afterward. Per the model in `simulation/aegis_radiation_force_feasibility.py`, radiation force starts clearing the 10 kBT barrier around roughly 125-165nm — so a redesign that agglomerates 10-50nm particles past ~150nm and then pushes the larger result looked, at the time, consistent with the current code's physics. **This initial judgment was made before examining agglomeration's own concentration dependence, and [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md) revised it sharply downward once that was checked.**

## 이후 진행 상황 / What happened next

이 문서에 기록된 초기 추정을 계기로 [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md)에서 실제 문헌 조사와 [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py) 정량 계산을 수행했습니다. 결과 요약은 [`README.md`](README.md)의 상태 표를 참고하세요.

The initial estimates recorded here prompted the literature review and the quantitative calculation in [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py) documented in [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md). See the status table in [`README.md`](README.md) for the summary of what changed.
