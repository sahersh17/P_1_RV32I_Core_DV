# RV32I core design and verification

[![RTL verification](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/workflows/verify.yml)
[![External verification](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/workflows/external.yml/badge.svg?branch=main)](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/workflows/external.yml)

A five-stage SystemVerilog RV32I core and a single-cycle RTL baseline. Both use the same execute and load/store units. The pipelined core adds EX/MEM and MEM/WB forwarding, load-use stalls, and branch squashing. Both cores implement synchronous machine-mode traps, machine CSR instructions, and MRET. The [architecture specification](docs/spec.md) contains the memory protocol and block diagram.

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

The regression compares retirement PC, instruction and register writeback along with load addresses and every store address, lane mask and write data. The trap cases check handler entry, CSR state, return, and suppression of faulting or squashed side effects. It alternates immediate memory responses with cycles of fetch starvation and data backpressure. The default seed is 20261118. Run logs are written to `build/pipeline/simulation.log` and `build/single-cycle/simulation.log`.

## Run the upstream RV32I tests and Spike scoreboard

Use Linux or WSL with Python 3.12, Icarus Verilog, a RISC-V GNU ELF compiler, and Spike v1.1.0 built with `--enable-commitlog`. The workflow installs these dependencies and saves the logs, test reports, and reference signatures as job artifacts.

```bash
python -m pip install -r tb/requirements.txt
git clone --depth 1 --branch 3.10.0 https://github.com/riscv/riscv-arch-test.git build/riscv-arch-test
python tb/verify_external.py --arch-test build/riscv-arch-test
```

The runner executes the complete pinned `rv32i_m/I` source directory on both cores and compares the full signature for every ELF with Spike. A separate retirement scoreboard checks the bare-metal demo and eight reproducible randomized ELF programs. The four cocotb unit checks cover the ALU, register file, immediate extraction, and decoder. Use `--units-only` to run them by themselves.

## Verification status

| Check | Result |
| --- | --- |
| Pipelined and single-cycle differential regressions | 12 directed and 2,000 constrained-random programs per core, zero mismatches |
| ISA operations exercised | 47 of 47 instruction types tracked by the regression |
| Pipeline coverage | 10 of 10 bins including all four operand forwarding paths, load-use stalls, taken and untaken branches, both memory wait types, and simultaneous forwarding from two stages |
| Verilator lint | Passed with `-Wall` on both RTL tops |
| Generic synthesis | Passed Yosys synthesis and structural checks for the pipelined top |
| Formal | Eight pipeline and trap assertions proved with SymbiYosys and ABC PDR |
| Upstream RV32I architectural signatures | 39 of 39 tests passed per core using riscv-arch-test 3.10.0 |
| Spike retirement scoreboard | 648 instructions matched across nine ELF programs per core |
| cocotb unit tests | All four passed |

Formal checks cover aligned fetch, zero reads from x0, valid retirement writes, selected forwarded data, execute-slot invalidation after a squash or load-use bubble, stable outstanding data requests, and trap redirection without admitting the faulting instruction or younger instructions.

The RTL workflow retains coverage, synthesis, and formal proof logs. The external workflow retains cocotb reports, per-program results, and Spike signatures. See the [bug log](docs/bug-log.md) for the original trap and retirement regressions.

The [external verification run](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/runs/44378269344) contains the upstream signature results and Spike comparison logs. The [RTL verification run](https://github.com/sahersh17/P_1_RV32I_Core_DV/actions/runs/44378269439) contains coverage, synthesis, and proof evidence. The [Project 2 handoff](docs/handoff.md) lists the integration interface and synthesis inputs.
