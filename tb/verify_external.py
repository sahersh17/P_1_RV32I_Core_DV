"""Run datapath cocotb tests and compare both RV32I cores against Spike."""

import argparse
import json
from pathlib import Path
import random
import re
import subprocess
from xml.etree import ElementTree

from cocotb_tools.runner import get_runner

from elf_image import BASE, load_elf
from isa import COMPLETION, LOADS, STORES, encode
from run import randomized

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "external"
RTL = sorted((ROOT / "rtl").glob("*.sv"))
SW = ROOT / "sw"
UNITS = {
    "alu": "rv32i_alu", "registers": "rv32i_regfile",
    "immediates": "rv32i_decode", "decoder": "rv32i_decode",
}
COMMIT = re.compile(r"^core\s+0:\s+3\s+(0x[0-9a-f]+)\s+\((0x[0-9a-f]+)\)(.*)$")
GPR_WRITE = re.compile(r"\bx\s*(\d+)\s+(0x[0-9a-f]+)\b")


def run_sim(top, name, module, *, testcase=None, cases=None):
    runner = get_runner("icarus")
    directory = BUILD / name
    runner.build(sources=RTL, hdl_toplevel=top, build_dir=directory,
                 parameters={"RESET_PC_WORD": BASE >> 2} if cases else {}, timescale=("1ns", "1ps"))
    path = runner.test(hdl_toplevel=top, test_module=module, testcase=testcase,
                       test_dir=ROOT / "tb", build_dir=directory, results_xml=str(directory / "results.xml"),
                       extra_env={"RV32I_ELF_CASES": str(cases)} if cases else {})
    results = ElementTree.parse(path)
    executed = results.findall(".//testcase")
    assert any(not case.findall("skipped") for case in executed), f"No tests executed for {name}"
    assert not results.findall(".//failure") and not results.findall(".//error"), f"Failed: {name}"


def build_elf(compiler, source, destination, env=None):
    args = [compiler, "-march=rv32i_zicsr", "-mabi=ilp32", "-DXLEN=32", "-nostdlib",
            "-nostartfiles", "-static", "-mno-relax", "-T", str(SW / "link.ld"), "-I", str(SW)]
    if env:
        cases = sorted(set(re.findall(r"\bTEST_CASE_\d+\b", source.read_text(encoding="utf-8"))))
        if not cases:
            raise ValueError(f"{source}: no architectural test cases detected")
        args.extend(["-I", str(env), *("-D" + case for case in cases)])
    subprocess.run([*args, str(source), "-o", str(destination)], check=True)


def spike_trace(log, tohost):
    trace = []
    for line in log.splitlines():
        match = COMMIT.match(line)
        if not match:
            continue
        pc, insn = (int(part, 16) for part in match.group(1, 2))
        if not trace and pc != BASE:
            continue
        rest = match[3]
        write = GPR_WRITE.search(rest)
        rd = int(write[1]) if write else 0
        value = int(write[2], 16) if rd else 0
        trace.append([pc, insn, rd, value])
        if insn & 0x7f == 0x23 and re.search(rf"\bmem\s+0x{tohost:08x}\b", rest):
            return trace
    raise ValueError("Spike commit log did not reach the tohost store")


def prepare_case(args, name, source, *, env=None, trace=False):
    elf = BUILD / f"{name}.elf"
    build_elf(args.compiler, source, elf, env)
    _, start, end, tohost = load_elf(elf)
    sig = BUILD / f"{name}.spike.sig"
    sig.unlink(missing_ok=True)
    command = [args.spike, "--isa=RV32I_Zicsr", "--priv=m", "-m4"]
    if trace:
        command += ["-l", "--log-commits"]
    log_path = BUILD / f"{name}.spike.log"
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run([*command, f"+signature={sig}", "+signature-granularity=4", str(elf)],
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)
    words = [int(line, 16) for line in sig.read_text(encoding="ascii").splitlines()]
    if len(words) != (end - start) // 4:
        raise ValueError(f"{name}: Spike emitted a wrong-length signature")
    result = {"name": name, "elf": str(elf), "cycle_limit": 300_000, "signature": words}
    if trace:
        result["trace"] = spike_trace(log_path.read_text(encoding="utf-8"), tohost)
    return result


def write_random_assembly(path, seed):
    program = randomized(random.Random(seed))
    # Rebase the existing arithmetic/memory/branch generator for a shared ELF address space.
    body = program[2:program.index(COMPLETION)]
    words = []
    for op, rd, rs1, operand in body:
        if op == "ecall":
            break
        if op in LOADS or op in STORES:
            rs1 = 30
        words.append(f"    .word {encode(op, rd, rs1, operand):#010x}")
    path.write_text(
        '#include "model_test.h"\n.section .text.init\n.globl rvtest_entry_point\n'
        'rvtest_entry_point:\n    la x30, scratch\n'
        + "\n".join(words)
        + '\n    la t6, begin_signature\n    sw x5, 0(t6)\n    RVMODEL_HALT\n'
        '.section .data\n.balign 16\nscratch: .space 64\n'
        'RVMODEL_DATA_BEGIN\n    .word 0\nRVMODEL_DATA_END\n',
        encoding="ascii",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch-test", type=Path, help="riscv-arch-test 3.10.0 checkout")
    parser.add_argument("--compiler", default="riscv64-unknown-elf-gcc")
    parser.add_argument("--spike", default="spike")
    parser.add_argument("--units-only", action="store_true")
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    for test, top in UNITS.items():
        run_sim(top, test, "cocotb_units", testcase=test)
    if args.units_only:
        return

    tests = [prepare_case(args, "smoke", SW / "smoke.S", trace=True)]
    if tests[0]["signature"][:3] != [55, 56, 11]:
        raise ValueError("Spike smoke signature did not contain the expected sum and trap cause")
    for seed in range(8):
        name = f"random-spike-{seed}"
        source = BUILD / f"{name}.S"
        write_random_assembly(source, seed)
        tests.append(prepare_case(args, name, source, trace=True))

    architectural = []
    if args.arch_test:
        suite = args.arch_test.resolve() / "riscv-test-suite"
        sources = sorted((suite / "rv32i_m" / "I" / "src").glob("*.S"))
        if not sources:
            raise ValueError(f"No RV32I architectural assembly sources under {suite}")
        for source in sources:
            architectural.append(prepare_case(args, "arch-" + source.stem, source, env=suite / "env"))
        tests.extend(architectural)

    cases = BUILD / "elf-cases.json"
    cases.write_text(json.dumps(tests), encoding="utf-8")
    for top in ("rv32i_core", "rv32i_single_cycle"):
        run_sim(top, top, "cocotb_elf", cases=cases)
    compared = sum(len(case.get("trace", ())) for case in tests)
    summary = {"unit_tests": len(UNITS), "architectural_tests_per_core": len(architectural),
               "spike_instruction_comparisons_per_core": compared,
               "spike_trace_programs_per_core": 9, "cores": 2}
    (BUILD / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
