# RV32I core design and verification

A five-stage SystemVerilog RV32I core and a single-cycle RTL baseline. Both use the same execute and load/store units. The pipelined core adds EX/MEM and MEM/WB forwarding, load-use stalls, and branch squashing. The [architecture specification](docs/spec.md) contains the memory protocol and block diagram.

## Run on Windows

Install Git, Python 3.9+, an [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) build containing Verilator, and a MinGW-w64 C++ compiler with C++20 and `g++` on PATH. The PowerShell runner builds with Verilator and compares the simulation against the Python ISA model.

```powershell
./scripts/run.ps1 -RandomPrograms 2000
./scripts/run.ps1 -SingleCycle -RandomPrograms 2000
./scripts/run.ps1 -RandomPrograms 0 -Waves
gtkwave build/pipeline/core.vcd
```

Pass `-CadRoot C:/path/to/oss-cad-suite` if you extracted the suite outside your Downloads folder. GTKWave is optional for viewing the trace.

## Run on Linux or WSL

With Python 3.9+ and the OSS CAD Suite available on PATH, run these from the project root.

```bash
python3 tb/run.py --random 2000
python3 tb/run.py --single-cycle --random 2000
verilator --lint-only -Wall --top-module rv32i_core rtl/*.sv
verilator --lint-only -Wall --top-module rv32i_single_cycle rtl/*.sv
yosys -Q -T -s scripts/synth.ys
(cd formal && sby -f core.sby)
```

The regression compares retirement PC, instruction and register writeback along with every store address, lane mask and write data. It alternates immediate memory responses with cycles of fetch starvation and data backpressure. The default seed is 20261118. Run logs are written to `build/pipeline/simulation.log` and `build/single-cycle/simulation.log`.

## Verification status

| Check | Result |
| --- | --- |
| Pipelined and single-cycle differential regressions | Each passed 7 directed and 2,000 constrained-random programs, with 135,993 retirements and 10,243 stores per core |
| ISA operations exercised | 40 of 40 implemented instruction types |
| Pipeline coverage | 10 of 10 bins including all four operand forwarding paths, load-use stalls, taken and untaken branches, both memory wait types, and simultaneous forwarding from two stages |
| Verilator lint | Passed with `-Wall` on both RTL tops |
| Generic synthesis | Passed Yosys synthesis and structural checks for the pipelined top |
| Formal | Six safety properties passed with SymbiYosys and ABC PDR |

Formal checks cover aligned fetch, zero reads from x0, valid retirement writes, selected forwarded data, execute-slot invalidation after a squash or load-use bubble, and stable outstanding data requests.

The GitHub Actions workflow runs lint, short regressions for both cores, synthesis, and formal verification. Official [RISC-V Architectural Certification Tests](https://github.com/riscv/riscv-arch-test), Spike comparison, and cocotb unit tests are pending. The current cores halt on faults and system calls, so certification tests that expect architectural trap handling need a corresponding design and harness update.
