# 문서 사용 안내 / Document Guide

> **제품·고객 적용 판정: NO-GO.** 이 디렉터리의 문서는 계산·분석 준비성과 아직 충족하지 못한 증거를 기록합니다. 고객 성능 약속, 제품 사양, 구매·투자, fab 통합, 안전·규제 적합성 또는 생산 적용 근거가 아닙니다.
>
> **Product/customer-application verdict: NO-GO.** The documents in this directory record computational/analytical readiness and evidence that is not yet met. They are not a basis for customer performance commitments, product specifications, procurement/investment, fab integration, safety/regulatory compliance, or production deployment.

## 현재 권위 순서 / Current order of authority

1. [`Aegis_Acoustics_B2B_Whitepaper.md`](Aegis_Acoustics_B2B_Whitepaper.md): 현재 권위 있는 한계 백서 원문 — *the current authoritative limits-whitepaper source.*
2. [`FEASIBILITY_EVIDENCE.md`](FEASIBILITY_EVIDENCE.md): 주장별 증거와 재현 명령 — *per-claim evidence and reproduction commands.*
3. [`MODEL_SELECTION.md`](MODEL_SELECTION.md): 나노입자 모델 선택과 적용성 gap — *nanoparticle model selection and applicability gaps.*
4. [`Aegis_Acoustics_B2B_Whitepaper.pdf`](Aegis_Acoustics_B2B_Whitepaper.pdf): Markdown 원문에서 생성한 배포용 읽기 사본 — *a distribution reading copy generated from the Markdown source.*

Markdown과 PDF에는 같은 문서 ID `AEGIS-FEASIBILITY-LIMITS-2026-08-21-R1`이 표시돼야 합니다. 의미가 다르면 Markdown을 기준으로 하고 PDF 배포를 중단한 뒤 다시 생성합니다. 과거 revision의 PDF는 현재 증거가 아니며 재사용하지 않습니다.

The Markdown and the PDF must display the same document ID, `AEGIS-FEASIBILITY-LIMITS-2026-08-21-R1`. If they diverge, the Markdown is authoritative: stop distributing the PDF and regenerate it. A PDF from a past revision is not current evidence and must not be reused.

## 탐색적 후속 트랙 / Exploratory follow-on track

위 "현재 권위 순서"는 백서 본문이 정의하는 원래 아키텍처(순수 음향 방사력 차단)에 대한 것입니다. [`hybrid/`](hybrid/README.md) 폴더는 그 아키텍처가 부딪힌 물리적 장벽에 대한 대안으로 제안된 하이브리드(응집+push) 경로를 문헌·정량 계산으로 검증한 **탐색적** 기록이며, 위 권위 순서와 별개입니다. 백서의 NO-GO 판정과 증거 등급 원칙은 이 폴더에도 동일하게 적용됩니다.

The "current order of authority" above concerns the original architecture (pure acoustic radiation-force exclusion) defined by the whitepaper's body. The [`hybrid/`](hybrid/README.md) folder is an **exploratory** record checking a hybrid (agglomerate + push) alternative — proposed in response to that architecture's physical barrier — against literature and a quantitative calculation, and it sits outside the authority order above. The whitepaper's NO-GO verdict and evidence-grading principles apply there equally.

## 배포 전 확인 / Pre-distribution checklist

- 첫 페이지에 `제품·하드웨어 성능 미검증`, `제품 및 고객 적용 NO-GO`, `하드웨어 실측 데이터 0건`이 보이는지 확인합니다.
  *Confirm the first page shows `제품·하드웨어 성능 미검증` (product/hardware performance unverified), `제품 및 고객 적용 NO-GO`, and `하드웨어 실측 데이터 0건` (zero hardware measurements).*
- `0.406°`, `69.444 ns`, `124.8 nm`, `23 + 23`, `약 0.83`을 해당 한계 문장 없이 떼어내지 않습니다.
  *Never quote `0.406°`, `69.444 ns`, `124.8 nm`, `23 + 23`, or `약 0.83` (approx. 0.83) without their accompanying limitation sentence.*
- `passed`, `verified`, `validated`를 장치 성능 의미로 바꾸지 않습니다.
  *Do not reinterpret `passed`, `verified`, or `validated` as device-performance claims.*
- 10–50 nm 차단, HVAC 대체, wafer 이송, 안전·규제 적합성, 에너지·수율·ROI 주장을 추가하지 않습니다.
  *Do not add claims of 10-50 nm exclusion, HVAC replacement, wafer transport, safety/regulatory compliance, or energy/yield/ROI benefits.*
- release tag, source commit, 입력·출력 artifact와 실행 환경이 없으면 역사적 benchmark로 표시하지 않습니다.
  *Do not label a number a historical benchmark without a release tag, source commit, input/output artifacts, and the execution environment.*

PDF 생성 도구가 바뀌더라도 원문 의미와 첫 페이지 경고가 보존돼야 합니다. `make whitepaper-pdf`는 한글 지원 font가 없으면 실패하고, Markdown과 renderer의 SHA-256·문서 ID·NO-GO를 PDF metadata에 결합합니다. `make whitepaper-check`는 기존 PDF가 현재 Markdown과 renderer에 일치하는지 검사합니다. 문서 계약 회귀 검사는 `python3 -m unittest -v tests.test_documentation_contract tests.test_whitepaper_pdf`로 실행합니다.

Even if the PDF-generation tool changes, the source meaning and first-page warnings must be preserved. `make whitepaper-pdf` fails closed without a Hangul-capable font, and it binds the Markdown's and renderer's SHA-256, the document ID, and NO-GO into the PDF metadata. `make whitepaper-check` verifies that the existing PDF matches the current Markdown and renderer. Run the documentation-contract regression checks with `python3 -m unittest -v tests.test_documentation_contract tests.test_whitepaper_pdf`.
