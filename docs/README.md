# 문서 사용 안내

> **제품·고객 적용 판정: NO-GO.** 이 디렉터리의 문서는 계산·분석 준비성과 아직 충족하지 못한 증거를 기록합니다. 고객 성능 약속, 제품 사양, 구매·투자, fab 통합, 안전·규제 적합성 또는 생산 적용 근거가 아닙니다.

## 현재 권위 순서

1. [`Aegis_Acoustics_B2B_Whitepaper.md`](Aegis_Acoustics_B2B_Whitepaper.md): 현재 권위 있는 한계 백서 원문
2. [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md): 주장별 증거와 재현 명령
3. [`MODEL_SELECTION.md`](MODEL_SELECTION.md): 나노입자 모델 선택과 적용성 gap
4. [`Aegis_Acoustics_B2B_Whitepaper.pdf`](Aegis_Acoustics_B2B_Whitepaper.pdf): Markdown 원문에서 생성한 배포용 읽기 사본

Markdown과 PDF에는 같은 문서 ID `AEGIS-FEASIBILITY-LIMITS-2026-08-21-R1`이 표시돼야 합니다. 의미가 다르면 Markdown을 기준으로 하고 PDF 배포를 중단한 뒤 다시 생성합니다. 과거 revision의 PDF는 현재 증거가 아니며 재사용하지 않습니다.

## 배포 전 확인

- 첫 페이지에 `제품·하드웨어 성능 미검증`, `제품 및 고객 적용 NO-GO`, `하드웨어 실측 데이터 0건`이 보이는지 확인합니다.
- `0.406°`, `69.444 ns`, `124.8 nm`, `23 + 23`, `약 0.83`을 해당 한계 문장 없이 떼어내지 않습니다.
- `passed`, `verified`, `validated`를 장치 성능 의미로 바꾸지 않습니다.
- 10–50 nm 차단, HVAC 대체, wafer 이송, 안전·규제 적합성, 에너지·수율·ROI 주장을 추가하지 않습니다.
- release tag, source commit, 입력·출력 artifact와 실행 환경이 없으면 역사적 benchmark로 표시하지 않습니다.

PDF 생성 도구가 바뀌더라도 원문 의미와 첫 페이지 경고가 보존돼야 합니다. `make whitepaper-pdf`는 한글 지원 font가 없으면 실패하고, Markdown과 renderer의 SHA-256·문서 ID·NO-GO를 PDF metadata에 결합합니다. `make whitepaper-check`는 기존 PDF가 현재 Markdown과 renderer에 일치하는지 검사합니다. 문서 계약 회귀 검사는 `python3 -m unittest -v tests.test_documentation_contract tests.test_whitepaper_pdf`로 실행합니다.
