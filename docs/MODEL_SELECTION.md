# 나노입자 모델 선택 기록 / Nanoparticle Model Selection Record

이 기록은 [`사전 하드웨어 타당성·한계 백서`](Aegis_Acoustics_B2B_Whitepaper.md)와 [`증거 매트릭스`](FEASIBILITY_EVIDENCE.md)의 모델 근거 부록입니다. 여기의 모델 검토는 Aegis 하드웨어 성능 검증이 아닙니다.

This record is a model-rationale appendix to the [Pre-Hardware Feasibility & Limits Whitepaper](Aegis_Acoustics_B2B_Whitepaper.md) and the [Evidence Matrix](FEASIBILITY_EVIDENCE.md). The model review here is not a validation of Aegis hardware performance.

> 아래 결정은 직접 방사력 차단 아키텍처에 대한 것입니다. 이 결정에서 드러난 continuum-적용성 gap을 우회하려는 하이브리드(응집+push) 대안은 별도 탐색 트랙인 [`hybrid/`](hybrid/README.md)에서 문헌·정량 계산으로 검증했으며, cleanroom 농도 조건에서는 다른(더 심각한) 장벽에 부딪힘을 확인했습니다.
>
> The decision below concerns the direct radiation-force exclusion architecture. A hybrid (agglomerate + push) alternative that attempts to route around the continuum-applicability gap surfaced here was checked against literature and a quantitative calculation in the separate exploratory track [`hybrid/`](hybrid/README.md), where it was found to run into a different — and more severe — barrier under cleanroom concentration conditions.

## 결정 / Decision

현재의 inviscid Gor'kov 계산은 수식 회귀와 크기·압력 scaling을 확인하는 기준 모델로만 유지합니다. 10–300 nm 공기 입자의 정량 예측기로 승격하지 않습니다.

The current inviscid Gor'kov calculation is retained only as a reference model for checking formula regression and size/pressure scaling. It is not promoted to a quantitative predictor for 10-300 nm airborne particles.

thermoviscous 연속체 이론을 즉시 덧붙이는 것도 보류합니다. Settnes–Bruus의 viscous 모델과 Karlsen–Bruus의 thermoviscous 모델은 acoustic boundary layer가 입자 반경과 비슷하거나 더 큰 경우를 다루지만, 연속체 유체 방정식과 입자 표면 경계조건을 사용합니다. 현재 기본 조건에서 계산되는 particle Knudsen number `lambda/a`는 10–300 nm에 대해 약 13.2–0.44이므로, no-slip 연속체 scattering 결과를 이 범위의 정량값으로 사용하는 것은 정당화되지 않습니다.

Bolting on thermoviscous continuum theory immediately is also deferred. The Settnes-Bruus viscous model and the Karlsen-Bruus thermoviscous model handle cases where the acoustic boundary layer is comparable to or larger than the particle radius, but they use continuum fluid equations and particle-surface boundary conditions. Under the current default conditions, the computed particle Knudsen number `lambda/a` is roughly 13.2-0.44 across 10-300 nm, so treating no-slip continuum scattering results as quantitative values in this range is not justified.

Cunningham slip factor는 준정상 입자 drag 보정에는 사용할 수 있지만 acoustic scattering coefficient 자체를 교정하지 않습니다. 따라서 slip-corrected drag만 추가해 전체 acoustic force가 검증됐다고 표시하지 않습니다.

The Cunningham slip factor can be used to correct quasi-steady particle drag, but it does not correct the acoustic scattering coefficient itself. Accordingly, adding slip-corrected drag alone is not marked as validating the overall acoustic force.

## 외부 실험에서 가져올 수 있는 것 / What can be taken from external experiments

Imani와 Robert는 50–80 kHz 직사각형 flow-through 정상파 공진기에서 submicron aerosol 분포를 측정했고, 후속 연구에서는 분자 효과가 유의한 영역의 net force를 실험적으로 추정해 약 150 nm까지의 분리 가능성을 보고했습니다. 이는 다음 실험 크기와 측정 방법을 정하는 근거이지만 Aegis 개방형 배열, 수 cm standoff 또는 wafer 침착 저감률의 검증값으로 이전할 수 없습니다.

Imani and Robert measured submicron aerosol distributions in a 50-80 kHz rectangular flow-through standing-wave resonator, and a follow-up study experimentally estimated the net force in a regime where molecular effects are significant, reporting separation feasibility down to roughly 150 nm. This is grounds for choosing the next experimental particle sizes and measurement methods, but it cannot be transferred as a validated value for an Aegis open array, a multi-centimeter standoff, or a wafer deposition-reduction rate.

따라서 다음 정량 모델은 임의의 보정식이 아니라 실제 Aegis 챔버에서 얻은 다음 측정값으로 보정해야 합니다.

Consequently, the next quantitative model must be calibrated against the following measurements taken in an actual Aegis chamber, not an arbitrary correction formula.

1. 주파수별 3D pressure/phase field와 acoustic streaming 속도
   *Frequency-resolved 3D pressure/phase field and acoustic streaming velocity.*
2. 입자 크기별 시간 분해 displacement 또는 concentration profile
   *Time-resolved displacement or concentration profile by particle size.*
3. 유량, 온도, 압력, 습도, 가스 조성과 입자 전하
   *Flow rate, temperature, pressure, humidity, gas composition, and particle charge.*
4. 음장 ON/OFF의 paired deposition count와 blank
   *Paired deposition counts and blanks for the acoustic field ON/OFF.*

## 새 물리 모델의 병합 게이트 / Merge gate for a new physics model

다음 조건을 모두 만족해야 정량 예측 모델로 표시합니다.

A model is labeled a quantitative predictor only when all of the following are satisfied.

1. 구현 수식과 계수의 원 출처 및 pressure convention을 문서화합니다.
   *Document the original source of the implemented formulas and coefficients, and the pressure convention used.*
2. `ka`, particle Knudsen number, viscous/thermal boundary-layer 조건을 코드가 자동 판정합니다.
   *The code automatically evaluates `ka`, the particle Knudsen number, and the viscous/thermal boundary-layer conditions.*
3. 원 논문의 표 또는 figure에서 독립적으로 읽은 benchmark를 허용 오차 내 재현합니다.
   *Reproduce, within tolerance, a benchmark read independently from a table or figure in the original paper.*
4. 코드 작성에 사용하지 않은 Aegis 실험 데이터로 out-of-sample 오차를 보고합니다.
   *Report out-of-sample error against Aegis experimental data that was not used to write the code.*
5. force, streaming, drag/slip, Brownian diffusion, flow residence time과 deposition endpoint를 분리해 보고합니다.
   *Report force, streaming, drag/slip, Brownian diffusion, flow residence time, and the deposition endpoint separately.*

## 1차 출처 / Primary sources

- M. Settnes and H. Bruus, "Forces acting on a small particle in an acoustical field in a viscous fluid," *Physical Review E* 85, 016327 (2012), DOI: [10.1103/PhysRevE.85.016327](https://doi.org/10.1103/PhysRevE.85.016327)
- J. T. Karlsen and H. Bruus, "Forces acting on a small particle in an acoustical field in a thermoviscous fluid," *Physical Review E* 92, 043010 (2015), DOI: [10.1103/PhysRevE.92.043010](https://doi.org/10.1103/PhysRevE.92.043010)
- R. J. Imani and E. Robert, "Acoustic separation of submicron solid particles in air," *Ultrasonics* 63, 135-140 (2015), DOI: [10.1016/j.ultras.2015.06.021](https://doi.org/10.1016/j.ultras.2015.06.021)
- R. J. Imani and E. Robert, "Estimation of acoustic forces on submicron aerosol particles in a standing wave field," *Aerosol Science and Technology* 52, 57-68 (2018), DOI: [10.1080/02786826.2017.1383968](https://doi.org/10.1080/02786826.2017.1383968)
