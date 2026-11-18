# Project 2 RTL handoff

Use `rv32i_core` as the pipelined synthesis top. The active source list is in [scripts/synth.ys](../scripts/synth.ys). The single-cycle model and testbenches are verification inputs. The repository verifies the RTL and reports generic Yosys synthesis. Project 2 owns technology mapping, constraints, place and route, and physical sign-off.

- Clock with `clk` and use synchronous active-low reset. Set `RESET_PC_WORD` to the integration reset byte address divided by four.
- Connect instruction and data memories using the valid/ready protocol in the [RTL specification](spec.md). The data port accepts byte strobes. The interface uses an in-order response and has no access-error response signal.
- Install an aligned `mtvec` handler during boot before software can raise a trap. The core runs in machine mode and supports synchronous exceptions.
- Use `retire_*` for architectural trace capture. The legacy `halted` pin is tied low.

Run the two GitHub workflows on the selected RTL revision before handing off a netlist. Their artifacts contain regression coverage, the synthesis report, formal proof logs, the architectural signature comparison, and the Spike retirement scoreboard.
