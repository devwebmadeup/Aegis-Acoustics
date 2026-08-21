# 하이브리드 트랙 안내 / Hybrid Track Guide

> 이 폴더는 [`../Aegis_Acoustics_B2B_Whitepaper.md`](../Aegis_Acoustics_B2B_Whitepaper.md)가 정의하는 원래 아키텍처(순수 음향 방사력 차단)의 **탐색적 대안 트랙**을 다룹니다. 백서 본문·NO-GO 판정·증거 등급 원칙은 이 폴더의 문서에도 동일하게 적용되며, 여기 있는 어떤 내용도 하드웨어로 검증되지 않았습니다.
>
> This folder covers an **exploratory alternative track** to the original architecture (pure acoustic radiation-force exclusion) defined in [`../Aegis_Acoustics_B2B_Whitepaper.md`](../Aegis_Acoustics_B2B_Whitepaper.md). The whitepaper's body, its NO-GO verdict, and its evidence-grading principles apply equally here — nothing in this folder has been validated on hardware.

## 이 트랙이 왜 존재하는가 / Why this track exists

원래 아키텍처(10-50nm 입자를 수 cm 거리에서 순수 음향 방사력으로 직접 차단)는 근본적인 물리적 척도 장벽(continuum 이론이 성립하지 않는 Knudsen number 영역)에 부딪힙니다. GitHub Issue #1에서 "응집으로 유효 입자 크기를 키운 뒤 방사력으로 미는" 하이브리드 아키텍처를 대안으로 제안했고, 이 폴더는 그 대안을 실제 문헌·계산으로 검증한 기록입니다.

The original architecture (direct radiation-force exclusion of 10-50nm particles at multi-centimeter standoff) runs into a fundamental physical scale barrier (a Knudsen-number regime where continuum theory doesn't apply). GitHub Issue #1 proposed a hybrid architecture — "grow the effective particle size via agglomeration, then push it with radiation force" — as an alternative, and this folder records that alternative being checked against real literature and calculation.

## 문서 구성 / Contents

1. [`FEASIBILITY_ESTIMATES.md`](FEASIBILITY_ESTIMATES.md) — 하이브리드를 포함한 각 서브시스템의 최초 실현가능성 추정(주관적 판단, GitHub Issue #1의 내용). 정량 근거가 아니라 조사의 출발점입니다.
   *Initial feasibility estimates across subsystems, including the hybrid path (subjective judgment, from GitHub Issue #1). This is the starting point for the investigation, not quantitative evidence.*
2. [`AGGLOMERATION_RESEARCH.md`](AGGLOMERATION_RESEARCH.md) — 위 추정을 실제 문헌과 [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py) 계산으로 검증한 결과. **핵심 발견**: cleanroom의 극저 입자 농도 때문에 응집 기반 접근은 배기가스 문헌 대비 약 10¹⁴배 느립니다.
   *The above estimates checked against real literature and calculations in [`simulation/aegis_agglomeration_timescale.py`](../../simulation/aegis_agglomeration_timescale.py). **Key finding**: because of a cleanroom's extremely low particle concentration, the agglomeration-based approach is about 10¹⁴x slower than the exhaust-gas literature it was validated in.*

## 현재 상태 요약 / Current status summary

| 경로 / Path | 상태 / Status |
|---|---|
| 정상 상태 cleanroom 응집<br>Steady-state cleanroom agglomeration | **~2-5%** — 정량 계산으로 사실상 정지 확인<br>Quantitatively confirmed as effectively inert |
| 국소 버스트 이벤트 대응 (미검증 가설)<br>Localized burst-event response (untested hypothesis) | **~20-30%** — 유일하게 남은 유망 경로, 실측 데이터 없음<br>The only remaining promising path; no measured data yet |
| 음향+정전기 하이브리드 재설계<br>Acoustic+electrostatic hybrid redesign | **~15-20%** — ESD 안전 게이트 추가 필요<br>Requires an additional ESD safety gate |

이 세 수치는 모두 이 폴더 문서에서 도출된 **비공식 판단**이며, [`../FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md)의 증거 등급 체계로 검증된 값이 아닙니다.

All three numbers above are **informal judgments** derived within this folder's documents, not values validated under the evidence-grading system in [`../FEASIBILITY_EVIDENCE.md`](../FEASIBILITY_EVIDENCE.md).
