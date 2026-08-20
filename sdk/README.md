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
