# 하이브리드 음향 응집 경로 조사 기록 / Hybrid Acoustic-Agglomeration Research Note

이 기록은 [`MODEL_SELECTION.md`](../MODEL_SELECTION.md)의 후속 조사입니다. GitHub Issue #1에서 "음향 응집(agglomeration)으로 유효 입자 크기를 키운 뒤 방사력으로 push"하는 하이브리드 아키텍처를 실현가능성이 더 높은 경로(~25-35%)로 제안했었고, 이 문서는 그 추정을 실제 문헌으로 검증한 결과입니다. **이 문서는 새 아키텍처를 채택하겠다는 결정이 아니라 조사 기록이며, Aegis 하드웨어로 아무것도 검증되지 않았다는 원칙은 동일하게 적용됩니다.**

This is a follow-up investigation to [`MODEL_SELECTION.md`](../MODEL_SELECTION.md). GitHub Issue #1 proposed a hybrid architecture — "grow the effective particle size via acoustic agglomeration, then push it with radiation force" — as the more feasible path (~25-35%). This document checks that estimate against actual literature. **This is a research note, not a decision to adopt a new architecture, and the same principle applies: nothing here is validated on Aegis hardware.**

## 요약 판단 / Summary verdict

문헌 조사 결과, 음향 응집 자체는 **[외부] 실증된 기술**이지만(산업 배기가스·화력발전 집진 등), Aegis가 실제로 막으려는 시나리오(초저농도 cleanroom 공기 중 드문 개별 킬러 디펙트 차단)에 그대로 옮기기는 **원래 예상보다 더 어렵다는 새로운 물리적 장벽**을 발견했습니다. 응집 메커니즘은 입자 농도의 제곱에 비례하는 충돌률에 의존하는데, cleanroom은 설계상 입자 농도가 극도로 낮기 때문입니다. 이 발견으로 "정상 상태 cleanroom 공기 중 응집" 경로의 추정치는 하향 조정하고, "국소 버스트 이벤트(그리퍼 마찰 등에서 순간적으로 발생하는 고농도 입자 구름) 포집"이라는 더 좁은 하위 시나리오로 재정의하는 것을 제안합니다.

The literature confirms acoustic agglomeration itself is an **[External], experimentally validated** technology (industrial exhaust treatment, coal-plant precipitation, etc.), but transferring it to what Aegis actually needs to prevent — rare individual killer defects in already-ultra-low-concentration cleanroom air — turns out to face **a physical barrier that was not obvious before this research**. The agglomeration mechanism depends on a collision rate that scales with the *square* of particle concentration, and a cleanroom is, by design, engineered to have extremely low particle concentration. This finding revises the "agglomeration in steady-state cleanroom air" estimate downward, and suggests reframing the candidate scenario more narrowly as "capturing localized burst events" (e.g., a transient particle cloud from gripper friction) rather than general ambient agglomeration.

## 1. 실증된 것 / What is experimentally established — [외부/External]

| 발견 / Finding | 수치 / Numbers | 출처 / Source |
|---|---|---|
| 음향 응집은 산업 배기/집진에서 실증된 전처리 기술<br>Acoustic agglomeration is a validated pretreatment step in industrial exhaust/precipitation | 미세먼지(PM2.5/PM1.5/PM0.5) 제거효율 85-95%<br>85-95% removal efficiency for PM2.5/PM1.5/PM0.5 | [Classification and Comparative Analysis of Acoustic Agglomeration Systems](https://doi.org/10.3390/asi8040116) |
| 저주파·고SPL이 표준 조건<br>Low frequency, high SPL is the standard operating condition | 44 Hz–30 kHz, 150-170 dB(≈632 Pa–6.3 kPa)<br>44 Hz-30 kHz, 150-170 dB SPL (≈632 Pa-6.3 kPa) | [Review of Acoustic Agglomeration Technology Research](https://pmc.ncbi.nlm.nih.gov/articles/PMC11112563/) |
| 디젤 배기 초미세입자(~100nm대)에서 실측 응집 성장<br>Measured agglomeration growth in diesel-exhaust ultrafine particles (~100nm range) | 평균 입경 96nm→121nm, 응집효율 최대 59.7%<br>Mean diameter 96nm→121nm, coagulation efficiency up to 59.7% | [Investigation of acoustic agglomeration on ultrafine particles chamber](https://pmc.ncbi.nlm.nih.gov/articles/PMC10360598/) |
| 23nm까지도 문헌에 등장하나 크기 의존적 효율 저하 확인<br>23nm appears in the literature, but size-dependent efficiency drop is confirmed | 21400Hz에서 10μm 입자 92.5% 감소 vs 0.3μm 입자 44.5% 감소 — 작을수록 급격히 비효율적<br>At 21400Hz, 92.5% reduction for 10μm vs 44.5% for 0.3μm — sharply less effective as size shrinks | [Symmetry 2021](https://doi.org/10.3390/sym13071200), [PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11112563/) |
| 음향+정전기 하이브리드가 단독 음향보다 뚜렷이 우수<br>Acoustic + electrostatic hybrid clearly outperforms acoustics alone | 전처리 결합 시 질량 제거효율 89.05%→99.28%; 일부 조합 98.3%까지 보고<br>Mass-removal efficiency rises from 89.05% to 99.28% with acoustic pre-conditioning; some combinations report up to 98.3% | [Acoustic-Electrostatic Hybridization](https://www.mdpi.com/2076-3417/16/12/5982), [PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11112563/) |
| 저농도/단분산 입자에는 별도 메커니즘 필요<br>A different mechanism is needed for low-concentration/monodisperse particles | Orthokinetic 충돌은 입자 크기가 서로 달라야 작동(단분산에는 무력); 단분산에는 acoustic wake/hydrodynamic 상호작용이 지배적이며 이는 주로 >0.5μm에서 검증됨<br>Orthokinetic collision requires differing particle sizes (ineffective for monodisperse populations); for monodisperse particles, the acoustic wake/hydrodynamic interaction dominates, and this is validated mainly above 0.5μm | [Orthokinetic collision, wake, gravity effects](https://www.sciencedirect.com/science/article/abs/pii/S0021850205000947), [PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11112563/) |

## 2. 새로 발견한 핵심 장벽 / The key barrier this research surfaced

**충돌률은 입자 농도의 제곱에 비례합니다 (coagulation rate ∝ n²).** 위 실증 데이터는 전부 디젤 배기·화력발전 배가스처럼 입자 농도가 매우 높은(대략 10⁶–10⁹ particles/cm³) 환경에서 나온 것입니다. 반면 Aegis가 보호하려는 cleanroom/EFEM 공기는 정의상 입자 농도가 극도로 낮도록(ISO class 1-5, 대략 1–100,000 particles/m³) 설계되어 있습니다. 이는 배기 환경보다 여러 자릿수 낮은 농도이며, 응집이 의존하는 충돌률이 농도의 제곱으로 줄어드는 만큼, 정상 상태 cleanroom 공기에서 응집이 유의미한 시간 내에 일어날 가능성은 실증 문헌의 조건과 근본적으로 다릅니다.

**Coagulation rate scales with the square of particle concentration (n²).** All the validated data above comes from environments with very high particle concentration (roughly 10⁶-10⁹ particles/cm³) — diesel exhaust, coal-plant flue gas. Aegis's actual target, cleanroom/EFEM air, is by definition engineered to have extremely low particle concentration (ISO class 1-5, roughly 1-100,000 particles/m³) — many orders of magnitude lower. Because the collision rate that agglomeration depends on falls with the *square* of concentration, whether meaningful agglomeration happens on a useful timescale in steady-state cleanroom air is a fundamentally different question than what the validated literature actually tested.

또한 Aegis가 막으려는 대표 시나리오는 "이미 오염된 공기를 정화"하는 것이 아니라 "드문 개별 킬러 디펙트 하나가 웨이퍼에 닿기 전에 차단"하는 것입니다. 응집은 주변에 충돌할 다른 입자가 있어야 작동하는데, 정의상 청정한 공기 중의 외로운 입자 하나는 응집 상대가 거의 없습니다. 따라서 "정상 상태 cleanroom 공기 중 응집" 시나리오는 원래 제안보다 낮게 재평가해야 합니다.

Also, the scenario Aegis is actually built for isn't "purify already-contaminated air" — it's "intercept one rare, individual killer defect before it reaches the wafer." Agglomeration needs other particles nearby to collide with, and a lone particle in air that is clean by definition has almost no partner to agglomerate with. So the "agglomeration in steady-state cleanroom air" scenario should be rated lower than originally proposed.

### 정량 확인 — [코드/합성] / Quantitative confirmation — [Code/Synthetic]

이 직관을 [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py)로 실제 계산했습니다. Smoluchowski/Fuchs Brownian coagulation kernel(연속체 형태, Cunningham slip correction 포함)로 두 입자가 확산만으로 서로를 찾는 데 걸리는 시간을 구하고, ISO 14644-1 cleanroom 등급의 농도 한도(0.1µm 기준, 더 작은 입자에는 상한 근사치로만 사용)와 문헌의 배기가스 농도 범위(~10⁶-10⁹ particles/cm³)를 같은 커널로 비교했습니다.

We checked this intuition with actual numbers using [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py). It computes how long two particles take to find each other by diffusion alone, using the Smoluchowski/Fuchs Brownian coagulation kernel (continuum form with Cunningham slip correction), and compares ISO 14644-1 cleanroom concentration limits (at the 0.1µm threshold, used only as an upper-bound proxy for our smaller target particles) against the literature's exhaust-gas concentration range (~10⁶-10⁹ particles/cm³) using the same kernel.

**결과 (10nm 입자, 순수 확산 기준, 음향/정전기 보조 없음):**

- **ISO Class 1** (Aegis 문서가 FOUP 내부 목표로 언급한 등급): 개체군이 절반으로 줄어드는 데 **약 471,000년**
- **ISO Class 5** (구 Class 100, 훨씬 느슨한 등급): 그래도 **약 47년**
- **문헌의 배기가스 농도 범위**: 0.15초–2.5분

**Results (10nm particles, pure diffusion, no acoustic/electrostatic assist):**

- **ISO Class 1** (the grade Aegis's own documents cite as the FOUP-interior target): population half-life of **~471,000 years**
- **ISO Class 5** (old Class 100, a far looser grade): still **~47 years**
- **The literature's exhaust-concentration range**: 0.15 seconds to 2.5 minutes

즉 cleanroom은 문헌이 실증한 배기가스 환경보다 이 메커니즘을 **약 10¹⁴배** 느리게 만듭니다. 이건 "엔지니어링으로 개선할 수 있는 격차"가 아니라 "순수 확산 기반 응집이 사실상 정지해 있다"는 규모입니다. 어떤 현실적인 음향/정전기 보조로도 이만한 자릿수 격차를 메우기는 매우 어렵습니다 — 문헌의 하이브리드 보조 효율 향상은 기껏해야 수 배~수십 배(89%→99.28% 같은 퍼센트 단위 개선) 수준이지, 10¹⁴배 규모가 아닙니다.

In other words, a cleanroom slows this mechanism down by roughly **10¹⁴x** relative to the exhaust environments where it was experimentally validated. That is not an "engineering gap you close with better hardware" — it's a scale at which pure-diffusion agglomeration is effectively frozen. No realistic acoustic/electrostatic assist closes a gap of that many orders of magnitude — the hybrid efficiency gains found in the literature are multiplicative factors of a few to a few dozen (percentage-point improvements like 89%→99.28%), not 10¹⁴x.

## 3. 재평가 / Revised assessment

| 시나리오 / Scenario | 이전 추정<br>Prior estimate | 조사 후 추정<br>Post-research estimate | 근거 / Reasoning |
|---|---|---|---|
| 정상 상태 cleanroom 공기에서 음향 응집으로 산발적 개별 입자를 성장시켜 차단<br>Acoustic agglomeration of sporadic individual particles in steady-state cleanroom air | ~25-35% | **~2-5%** | 정량 계산 결과 ISO Class 1에서 반감기 약 471,000년(순수 확산 기준) — 배기가스 대비 약 10¹⁴배 느림. 이는 엔지니어링 격차가 아니라 메커니즘이 사실상 정지한 규모.<br>Quantitative calculation shows a ~471,000-year half-life at ISO Class 1 (pure diffusion) — about 10¹⁴x slower than the exhaust-gas literature. This isn't an engineering gap; it's a scale at which the mechanism is effectively inert. |
| 국소 버스트 이벤트(그리퍼 마찰·기계적 충격 등으로 순간 발생하는 고농도 입자 구름) 포집·응집 후 push<br>Capturing a localized burst event (a transient high-concentration particle cloud from gripper friction/mechanical shock), agglomerating, then pushing | 검토 안 됨<br>Not previously considered | **~20-30%** | 발생원 인근은 국소적으로 농도가 높아 충돌률 문제가 완화됨. 다만 이 좁은 시나리오는 Aegis의 원래 목표(지속적 방어막)보다 범위가 훨씬 제한적이며, 문헌에 직접 대응하는 실증 사례는 없음.<br>Near the source, local concentration is transiently high enough to ease the n² problem. But this narrower scenario is much more limited in scope than Aegis's original goal (a continuous shield), and no literature directly validates this specific case. |
| 음향+정전기 하이브리드로 재설계 (지속 저농도 환경 가정)<br>Acoustic + electrostatic hybrid redesign (assuming continuous low-concentration operation) | 포함되어 있었음<br>Included in the prior estimate | **~15-20%** | 하이브리드 자체의 우수성(89%→99.28%)은 고농도 산업 환경에서 나온 수치이며 저농도 전이는 미검증. 게다가 정전기 요소는 반도체 fab의 ESD 리스크라는 새 안전 게이트를 추가함([`FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md) 6장 참고).<br>The hybrid's strong numbers (89%→99.28%) come from high-concentration industrial settings; transfer to low concentration is unverified. It also adds a new safety gate — ESD risk in a semiconductor fab (see Section 6 of [`FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md)). |
| 아키텍처 재사용성: 현재 SDK(위상 배열 beamforming, 40kHz-수MHz)가 응집 하드웨어에 그대로 쓰이는가<br>Architecture reuse: does the current SDK (phased-array beamforming, 40kHz-few MHz) carry over to agglomeration hardware | 암묵적으로 가정됨<br>Implicitly assumed | **낮음 / Low** | 실증된 응집 시스템은 44Hz-30kHz의 저주파·고SPL 단일/소수 채널 방식이며, Aegis의 256채널 MHz급 위상 배열과는 다른 transducer/driver 설계가 필요할 가능성이 높음.<br>Validated agglomeration systems use low-frequency (44Hz-30kHz), high-SPL, single/few-channel drive — likely a different transducer/driver design than Aegis's 256-channel, near-MHz phased array. |

## 4. 결론 / Conclusion

정성적 우려로 시작했던 것이 정량 계산으로 확인되면서 오히려 더 나쁜 소식이 됐습니다. 응집이라는 메커니즘 자체는 확실히 실증되어 있지만, Aegis의 실제 조건(ISO Class 1 cleanroom)에서 순수 확산 기반 응집은 반감기 47만 년, 배기가스 대비 10¹⁴배 느림이라는 정량 결과가 나왔습니다. 이는 하이브리드 보조로 메울 수 있는 격차가 아닙니다(문헌의 하이브리드 개선폭은 퍼센트 단위이지 자릿수 단위가 아님). 따라서 "정상 상태 cleanroom 공기 중 응집" 경로는 처음 제시한 25-35%에서 **~2-5%**로 크게 하향합니다. 이번 조사에서 유일하게 남는 유망한 하위 경로는 "지속적 방어막"이 아니라, 국소적으로 순간 농도가 훨씬 높을 수 있는 "국소 버스트 이벤트 대응"으로 스코프를 좁힌 경우(~20-30%, 다만 이는 아직 실측 데이터가 없는 별도 가설)입니다.

What started as a qualitative concern turned out worse once quantified. The agglomeration mechanism itself is solidly validated, but under Aegis's actual condition (an ISO Class 1 cleanroom), pure-diffusion agglomeration comes out to a 470,000-year half-life — about 10¹⁴x slower than the exhaust-gas literature. That is not a gap a hybrid assist can close (the hybrid improvements in the literature are percentage-point gains, not orders-of-magnitude gains). Accordingly, the "agglomeration in steady-state cleanroom air" path is revised sharply down from the original 25-35% to **~2-5%**. The only sub-path from this research that still looks promising is not "maintain a continuous shield" but a narrower scope — "respond to localized burst events," where transient local concentration could plausibly be much higher (~20-30%, though this remains an untested hypothesis with no measured data yet).

## 5. 다음 조사 후보 / Candidate next steps

1. ~~실제 cleanroom 입자 농도(ISO class별 particles/m³)와 산업 응집 문헌의 농도를 정량 비교해, n² 스케일링이 실제로 얼마나 느려지는지 order-of-magnitude 계산을 수행합니다.~~ **완료** — [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py)로 계산 완료 (위 3절 참고). 약 10¹⁴배 느림을 확인.
   *~~Quantitatively compare real cleanroom particle concentrations against the industrial agglomeration literature.~~* **Done** — computed in [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py) (see Section 3 above). Confirmed a ~10¹⁴x slowdown.
2. 그리퍼 마찰 등 국소 버스트 이벤트의 실제 순간 농도·지속시간 데이터를 찾아 "버스트 포집" 시나리오가 물리적으로 말이 되는지 확인합니다.
   *Look for real transient-concentration/duration data from localized burst events (e.g., gripper friction) to check whether the "burst capture" scenario is physically plausible.*
3. 저주파·고SPL 응집 구동 방식과 현재 256채널 phased-array SDK가 얼마나 다른 hardware를 요구하는지 설계 수준에서 gap 분석합니다.
   *Do a design-level gap analysis of how different a low-frequency, high-SPL agglomeration driver is from the current 256-channel phased-array SDK hardware.*
4. 정전기 보조를 추가할 경우 필요한 ESD/EMC 안전 평가 범위를 [`FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md)의 안전 게이트에 맞춰 스코핑합니다.
   *Scope the ESD/EMC safety-assessment work an electrostatic-assist addition would require, aligned with the safety gates in [`FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md).*

## 외부 근거 / External references

- Classification and Comparative Analysis of Acoustic Agglomeration Systems for Fine Particle Removal, *Applied System Innovation* (2025), DOI: [10.3390/asi8040116](https://doi.org/10.3390/asi8040116)
- Review of Acoustic Agglomeration Technology Research, *ACS Omega* (2024), [PMC11112563](https://pmc.ncbi.nlm.nih.gov/articles/PMC11112563/), DOI: [10.1021/acsomega.3c08815](https://pubs.acs.org/doi/10.1021/acsomega.3c08815)
- Investigation of the acoustic agglomeration on ultrafine particles chamber built into the exhaust system of an internal combustion engine, [PMC10360598](https://pmc.ncbi.nlm.nih.gov/articles/PMC10360598/)
- Application of Acoustic Agglomeration Technology to Improve the Removal of Submicron Particles from Vehicle Exhaust, *Symmetry* 13, 1200 (2021), DOI: [10.3390/sym13071200](https://doi.org/10.3390/sym13071200)
- The effects of orthokinetic collision, acoustic wake, and gravity on acoustic agglomeration of polydisperse aerosols, *J. Aerosol Science*, [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0021850205000947)
- Effect of Duct Inclination and Acoustic-Electrostatic Hybridization on Particle Removal in Low-Velocity Airflows, *Applied Sciences* 16(12), 5982 (2025), [MDPI](https://www.mdpi.com/2076-3417/16/12/5982)
- US Patent 5,681,396, "Method and apparatus for utilizing acoustic coaxing induced microcavitation for submicron particulate eviction" — semiconductor wafer wet-cleaning prior art, mechanistically distinct (immersed megasonic cavitation, not aerosol-phase agglomeration); [Google Patents](https://patents.google.com/patent/US5681396A/en)
- J. H. Seinfeld and S. N. Pandis, *Atmospheric Chemistry and Physics: From Air Pollution to Climate Change*, ch. 13 (Brownian coagulation kernel and Cunningham slip correction) — standard aerosol-physics reference used for the kernel implemented in [`aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py)
- ISO 14644-1:2015, *Cleanrooms and associated controlled environments — Part 1: Classification of air cleanliness by particle concentration* — source of the Cn = 10^N (0.1/D)^2.08 concentration-limit formula used as the cleanroom concentration proxy
