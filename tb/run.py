"""Generate RV32I programs and compare simulation with the ISA model."""

import argparse
import random
import subprocess
from pathlib import Path

from isa import BRANCHES, I_OPS, LOADS, R_OPS, STORES, encode, reference

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OPERATIONS = set(R_OPS + I_OPS + ("sub", "sra", "srai", "lui", "auipc", "jal", "jalr",
                                    "fence", "ecall", "ebreak")) | LOADS.keys() | STORES.keys() | BRANCHES.keys()
COVERAGE = ("EX/MEM to rs1", "EX/MEM to rs2", "MEM/WB to rs1", "MEM/WB to rs2",
            "Load-use stall", "Taken branch", "Not-taken branch", "Data wait",
            "Fetch wait", "EX/MEM rs1 with MEM/WB rs2")


def directed():
    # Consecutive writes, mixed bypasses, load-use, a backward loop, and squash sentinels.
    main = [
        ("addi", 1, 0, 7), ("addi", 2, 0, 11), ("add", 3, 2, 1), ("xor", 4, 2, 3),
        ("sw", 4, 0, 0), ("lw", 5, 0, 0), ("add", 6, 5, 5),
        ("beq", 8, 5, 5), ("sw", 2, 0, 4), ("bne", 8, 5, 5), ("addi", 7, 0, 3),
        ("addi", 7, 7, -1), ("bne", -4, 7, 0), ("jal", 8, 0, 8), ("illegal", 0, 0, 0),
        ("auipc", 9, 0, 0), ("jalr", 10, 9, 13), ("sw", 1, 0, 8),
        ("addi", 0, 0, 17), ("addi", 11, 0, -128), ("sb", 11, 0, 7),
        ("lb", 12, 0, 7), ("lbu", 13, 0, 7), ("sh", 11, 0, 10),
        ("lh", 14, 0, 10), ("lhu", 15, 0, 10), ("fence", 0, 0, 0), ("ebreak", 0, 0, 0),
    ]
    return [
        main, main[:-1] + [("ecall", 0, 0, 0)],
        [("lw", 1, 0, 1), ("sw", 0, 0, 8)],
        [("jal", 2, 0, 2), ("sw", 0, 0, 8)],
        [("illegal", 0, 0, 0), ("sw", 0, 0, 8)],
        [("sh", 0, 0, 1), ("sw", 0, 0, 8)],
        [("addi", 1, 0, 3), ("jalr", 2, 1, 0), ("sw", 0, 0, 8)],
    ]


def randomized(rng):
    arithmetic = R_OPS + I_OPS + ("sub", "sra", "srai", "lui", "auipc")
    operations = arithmetic + tuple(LOADS) + tuple(STORES) + tuple(BRANCHES)
    program = [("addi", rd, 0, rng.randint(-2048, 2047)) for rd in range(1, 8)]
    previous = 7
    for _ in range(64):
        op = rng.choice(operations)
        rd = rng.randrange(8)
        source = previous if rng.randrange(3) else rng.randrange(8)
        if op in LOADS or op in STORES:
            size = LOADS[op][1] if op in LOADS else STORES[op]
            instruction = (op, rd, 0, size * rng.randrange(64 // size))
        elif op in BRANCHES:
            instruction = (op, 8, source, rng.randrange(8))
        elif op in ("lui", "auipc"):
            instruction = (op, rd, 0, rng.getrandbits(20) << 12)
        elif op in I_OPS or op == "srai":
            immediate = rng.randrange(32) if op in ("slli", "srli", "srai") else rng.randint(-2048, 2047)
            instruction = (op, rd, source, immediate)
        else:
            instruction = (op, rd, source, rng.randrange(8))
        program.append(instruction)
        if op in arithmetic or op in LOADS:
            previous = rd
    program += [("fence", 0, 0, 0), ("ecall", 0, 0, 0)]
    return program


def parse_trace(lines):
    cases = []
    coverage = 0
    for line in lines:
        fields = line.split()
        if not fields:
            continue
        kind = fields[0]
        if kind == "CASE":
            if int(fields[1]) != len(cases):
                raise SystemExit(f"Unexpected case number in {line}")
            cases.append([])
        elif kind in ("STORE", "RETIRE"):
            values = [int(v, 10 if kind == "RETIRE" and pos == 2 else 16)
                      for pos, v in enumerate(fields[1:])]
            cases[-1].append((kind, *values))
        elif kind == "COVERAGE":
            coverage = int(fields[1], 16)
    return cases, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random", type=int, default=100, help="number of random programs")
    parser.add_argument("--seed", type=int, default=20261118)
    parser.add_argument("--waves", action="store_true")
    parser.add_argument("--single-cycle", action="store_true")
    parser.add_argument("--prebuilt", type=Path, help="use a prebuilt VVP image or simulator executable")
    args = parser.parse_args()
    if args.random < 0:
        parser.error("--random must be nonnegative")
    rng = random.Random(args.seed)
    programs = directed() + [randomized(rng) for _ in range(args.random)]
    work = BUILD / ("single-cycle" if args.single_cycle else "pipeline")
    work.mkdir(parents=True, exist_ok=True)
    expected = []
    isa_coverage = set()
    for index, program in enumerate(programs):
        words = [encode(*insn) for insn in program]
        words += [0] * (256 - len(words))
        (work / f"case{index:04d}.hex").write_text("".join(f"{word:08x}\n" for word in words), encoding="ascii")
        trace, covered = reference(program)
        expected.append(trace)
        isa_coverage.update(covered)
    if args.prebuilt:
        binary = args.prebuilt.resolve(strict=True)
        cmd = ["vvp", str(binary)] if binary.suffix == ".vvp" else [str(binary)]
    else:
        binary = work / "core.vvp"
        rtl = sorted((ROOT / "rtl").glob("*.sv"))
        definitions = ["-DSINGLE_CYCLE"] if args.single_cycle else []
        subprocess.run(["iverilog", "-g2012", "-Wall", "-s", "tb_core", "-o", str(binary), *definitions,
                        *map(str, rtl), str(ROOT / "tb/tb_core.sv")], check=True)
        cmd = ["vvp", str(binary)]
    cmd.append(f"+cases={len(programs)}")
    if args.waves:
        cmd.append("+waves")
    with (work / "simulation.log").open("w", encoding="ascii") as log:
        result = subprocess.run(cmd, cwd=work, stdout=log, stderr=subprocess.STDOUT)
    with (work / "simulation.log").open(encoding="ascii") as log:
        actual, coverage = parse_trace(log)
    if result.returncode or len(actual) != len(expected):
        raise SystemExit(f"Simulation exited with status {result.returncode} after {len(actual)} cases. See {work / 'simulation.log'}")
    for index, (got, wanted) in enumerate(zip(actual, expected)):
        for kind in ("STORE", "RETIRE"):
            got_kind = [event for event in got if event[0] == kind]
            wanted_kind = [event for event in wanted if event[0] == kind]
            if got_kind != wanted_kind:
                for offset, pair in enumerate(zip(got_kind, wanted_kind)):
                    if pair[0] != pair[1]:
                        raise SystemExit(f"Case {index}, {kind} {offset}: got {pair[0]}, expected {pair[1]}")
                raise SystemExit(f"Case {index}: got {len(got_kind)} {kind} events, expected {len(wanted_kind)}")
    retirements = sum(event[0] == "RETIRE" for trace in actual for event in trace)
    stores = sum(event[0] == "STORE" for trace in actual for event in trace)
    print(f"PASS: {len(programs)} programs, {retirements} retirements, {stores} stores, zero mismatches")
    missing = OPERATIONS - isa_coverage
    print(f"ISA coverage: {len(OPERATIONS) - len(missing)}/{len(OPERATIONS)}")
    if missing:
        print("Uncovered instructions:", ", ".join(sorted(missing)))
    for bit, name in enumerate(() if args.single_cycle else COVERAGE):
        print(f"{'hit' if coverage & (1 << bit) else 'miss'}  {name}")
    pipeline_covered = args.single_cycle or coverage == (1 << len(COVERAGE)) - 1
    if args.random >= 100 and (missing or not pipeline_covered):
        raise SystemExit("Coverage target missed")


if __name__ == "__main__":
    main()
