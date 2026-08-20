# Aegis C reference API

`aegis_core.c` is a stateless, allocation-free reference implementation of two calculations:

- multi-distance ToF regression with an optional shared timing offset;
- direct-path relative delay and wrapped phase generation for caller-supplied emitter coordinates.

All coordinates, distances, times and frequencies use SI units. Output buffers are allocated by the caller, must not overlap each other or the emitter array, and are checked through `capacity` before any element is written. The public ABI uses fixed-width status and flag types and requires IEEE-754 binary64 `double`.

The header publishes explicit numerical limits for calibration distance/time, sound speed, frequency and relative phase cycles. Values outside that reference domain fail instead of returning a low-precision phase.

Build a local shared library on a POSIX toolchain:

```bash
cc -std=c11 -Wall -Wextra -Wpedantic -Werror -fPIC -shared \
  -I sdk sdk/aegis_core.c -lm -o libaegis_core.so
```

The implementation is numerically compared with the Python reference by `tests/test_c_sdk.py`. This proves only the deterministic calculation and ABI exercise on the test host. It does not include sensor acquisition, a transducer driver, an RTOS safety state machine, channel transfer-function calibration, or hardware-in-the-loop validation.

---

# Aegis C 참조 API (한국어)

`aegis_core.c`는 다음 두 계산만 수행하는 stateless·allocation-free 참조 구현입니다.

- 공통 timing offset 옵션이 있는 다중 거리 ToF 회귀
- 호출자가 제공한 emitter 좌표에 대한 direct-path 상대 지연과 wrap된 위상 생성

모든 좌표·거리·시간·주파수는 SI 단위를 사용합니다. 출력 버퍼는 호출자가 할당하며, 서로 또는 emitter 배열과 겹칠 수 없고, 어떤 원소를 쓰기 전에 `capacity`로 먼저 검사됩니다. 공개 ABI는 고정폭 상태·플래그 타입을 사용하며 IEEE-754 binary64 `double`을 요구합니다.

헤더는 calibration 거리/시간, 음속, 주파수, 상대 위상 cycle에 대한 명시적 수치 한계를 공개합니다. 이 참조 범위를 벗어난 값은 저정밀 위상을 반환하는 대신 실패를 반환합니다.

POSIX 툴체인에서 로컬 공유 라이브러리를 빌드하는 방법:

```bash
cc -std=c11 -Wall -Wextra -Wpedantic -Werror -fPIC -shared \
  -I sdk sdk/aegis_core.c -lm -o libaegis_core.so
```

이 구현은 `tests/test_c_sdk.py`가 Python 참조 구현과 수치적으로 비교합니다. 이는 테스트 호스트에서의 결정론적 계산과 ABI 동작만을 증명하며, 센서 취득, transducer driver, RTOS 안전 상태 머신, 채널 전달함수 교정, hardware-in-the-loop 검증은 포함하지 않습니다.
