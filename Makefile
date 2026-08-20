PYTHON ?= python3
CC ?= cc
CXX ?= c++
MPLCONFIGDIR ?= /tmp/aegis-matplotlib
PYTHONPYCACHEPREFIX ?= /tmp/aegis-pycache

export MPLCONFIGDIR
export PYTHONPYCACHEPREFIX

.PHONY: verify phase-benchmark phase-uncertainty phase-measurement-example radiation-report deposition-power deposition-example c-sdk-check whitepaper-pdf whitepaper-check

verify: c-sdk-check
	$(PYTHON) -m unittest discover -s tests -v

c-sdk-check:
	$(CC) -I sdk -std=c11 -Wall -Wextra -Wpedantic -Wconversion -Werror -c sdk/aegis_core.c -o /tmp/aegis_core.o
	$(CXX) -I. -std=c++17 -Wall -Wextra -Wpedantic -Werror -include sdk/aegis_core.h -x c++ -fsyntax-only /dev/null

phase-benchmark:
	$(PYTHON) simulation/aegis_phase_calibration.py benchmark --iterations 1000 --budget-ms 100 --json --fail-on-budget

phase-uncertainty:
	$(PYTHON) simulation/aegis_phase_uncertainty.py --trials 2000 --seed 20260820 --json --fail-on-budget

phase-measurement-example:
	$(PYTHON) analysis/aegis_phase_measurement_analysis.py examples/phase_measurement_template.csv --summary-only --report-only

radiation-report:
	$(PYTHON) simulation/aegis_radiation_force_feasibility.py --no-show --no-plot --format json --diameters-nm 10,20,50,100,150,300

deposition-power:
	$(PYTHON) analysis/aegis_deposition_power.py verify examples/deposition_protocol_template.json

deposition-example:
	$(PYTHON) analysis/aegis_deposition_analysis.py examples/deposition_trial_template.csv --blank-policy paired_subtract --bootstrap-resamples 10000 --seed 77 --minimum-reduction 0.30 --minimum-independent-runs 6 --report-only

whitepaper-pdf:
	$(PYTHON) tools/render_whitepaper_pdf.py

whitepaper-check:
	$(PYTHON) tools/render_whitepaper_pdf.py --check
