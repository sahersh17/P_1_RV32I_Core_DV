"""Drive both external memory ports and check architectural retirement."""

import json
import os
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from elf_image import BASE, SIZE, load_elf
from isa import MASK, sx


def word_at(memory, address):
    offset = (address & ~3) - BASE
    if not 0 <= offset <= SIZE - 4:
        return 0
    return int.from_bytes(memory[offset:offset + 4], "little")


async def execute(dut, case):
    memory, start, end, tohost = load_elf(case["elf"])
    dut.clk.value = 0
    dut.reset_n.value = 0
    dut.imem_ready.value, dut.imem_rdata.value = 0, 0
    dut.dmem_ready.value, dut.dmem_rdata.value = 0, 0
    await Timer(5, unit="ns")
    dut.clk.value = 1
    await Timer(5, unit="ns")
    registers = [0] * 32
    trace = case.get("trace")
    retired = 0

    for cycle in range(case["cycle_limit"]):
        dut.clk.value = 0
        dut.reset_n.value = 1
        dut.imem_ready.value = cycle % 7 != 3
        dut.dmem_ready.value = cycle % 5 != 2
        dut.imem_rdata.value = word_at(memory, int(dut.imem_addr.value))
        await Timer(2, unit="ns")
        address = int(dut.dmem_addr.value) if int(dut.dmem_valid.value) else BASE
        dut.dmem_rdata.value = word_at(memory, address)
        await Timer(2, unit="ns")

        if int(dut.dmem_valid.value) and int(dut.dmem_ready.value):
            assert BASE <= address < BASE + SIZE, f"Unmapped data access at {address:#x}"
            if int(dut.dmem_write.value):
                mask = int(dut.dmem_wstrb.value)
                data = int(dut.dmem_wdata.value)
                offset = (address & ~3) - BASE
                for lane in range(4):
                    if mask & (1 << lane):
                        memory[offset + lane] = (data >> (lane * 8)) & 255

        if int(dut.retire_valid.value):
            pc, insn = int(dut.retire_pc.value), int(dut.retire_insn.value)
            we = int(dut.retire_we.value)
            rd = int(dut.retire_rd.value) if we else 0
            value = int(dut.retire_value.value) if we else 0
            record = [pc, insn, rd, value]
            if trace is not None:
                assert retired < len(trace), f"Unexpected retirement {record}"
                assert trace[retired] == record, (
                    f"{case['name']} retirement {retired}: DUT={record}, Spike={trace[retired]}"
                )
            retired += 1
            if rd:
                registers[rd] = value
            if insn & 0x7f == 0x23:
                base = registers[(insn >> 15) & 31]
                offset = sx((insn >> 25) << 5 | ((insn >> 7) & 31), 12)
                if (base + offset) & MASK == tohost:
                    assert word_at(memory, tohost) == 1, f"{case['name']}: unexpected tohost value"
                    assert trace is None or retired == len(trace), "Trace ended early"
                    signature = [
                        word_at(memory, address) for address in range(start, end, 4)
                    ]
                    expected = case["signature"]
                    assert len(signature) == len(expected), f"{case['name']}: signature length mismatch"
                    for index, (actual, wanted) in enumerate(zip(signature, expected)):
                        assert actual == wanted, (
                            f"{case['name']} signature word {index}: DUT={actual:08x}, Spike={wanted:08x}"
                        )
                    dut.clk.value = 1
                    await Timer(5, unit="ns")
                    return retired

        assert not int(dut.halted.value)
        dut.clk.value = 1
        await Timer(5, unit="ns")

    raise AssertionError(f"{case['name']} did not terminate after {case['cycle_limit']} cycles")


@cocotb.test()
async def bare_metal(dut):
    cases = json.loads(Path(os.environ["RV32I_ELF_CASES"]).read_text(encoding="utf-8"))
    for case in cases:
        retired = await execute(dut, case)
        dut._log.info("PASS %s (%d retired instructions, %d signature words)", case["name"],
                      retired, len(case["signature"]))
