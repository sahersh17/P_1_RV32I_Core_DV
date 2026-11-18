"""Directed and seeded unit checks for the shared datapath."""

import random

import cocotb
from cocotb.triggers import Timer

from isa import BRANCHES, CSR_OPS, MASK, encode, sx


async def settle():
    await Timer(5, unit="ns")


@cocotb.test()
async def alu(dut):
    rng = random.Random(31)
    vectors = [(0, 0), (MASK, 1), (0x80000000, 31), (0x7fffffff, 32)]
    vectors += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(30)]
    for a, b in vectors:
        amount = b % 32
        cases = [a + b, a << amount, sx(a, 32) < sx(b, 32), a < b,
                 a ^ b, a >> amount, a | b, a & b]
        for operation, expected in enumerate(cases):
            dut.a.value, dut.b.value = a, b
            dut.operation.value, dut.alternate.value = operation, 0
            await settle()
            assert int(dut.result.value) == expected & MASK
        for operation, expected in ((0, a - b), (5, sx(a, 32) >> amount)):
            dut.operation.value, dut.alternate.value = operation, 1
            await settle()
            assert int(dut.result.value) == expected & MASK


@cocotb.test()
async def registers(dut):
    rng = random.Random(32)
    model = [0] * 32
    dut.clk.value = 0
    dut.reset_n.value = 0
    dut.write_valid.value = 0
    dut.rs1.value, dut.rs2.value, dut.rd.value = 0, 0, 0
    dut.write_data.value = 0
    await settle()
    dut.clk.value = 1
    await settle()
    dut.clk.value = 0
    dut.reset_n.value = 1
    for rd in [*range(32), *(rng.randrange(32) for _ in range(100))]:
        rs1, rs2 = rd, rng.randrange(32)
        value = rng.getrandbits(32)
        enabled = rng.randrange(4) != 0 or rd == 0
        dut.rs1.value, dut.rs2.value, dut.rd.value = rs1, rs2, rd
        dut.write_valid.value, dut.write_data.value = enabled, value
        await settle()
        assert (int(dut.read_a.value), int(dut.read_b.value)) == (model[rs1], model[rs2])
        dut.clk.value = 1
        if enabled and rd:
            model[rd] = value
        await settle()
        assert (int(dut.read_a.value), int(dut.read_b.value)) == (model[rs1], model[rs2])
        dut.clk.value = 0


@cocotb.test()
async def immediates(dut):
    rng = random.Random(33)
    formats = [
        ("addi", 12, 1), ("sw", 12, 1), ("beq", 13, 2),
        ("jal", 21, 2), ("lui", 32, 4096),
    ]
    for op, width, step in formats:
        minimum, maximum = -(1 << (width - 1)), 1 << (width - 1)
        values = [minimum, maximum - step, -step, 0, step]
        values += [rng.randrange(minimum, maximum, step) for _ in range(32)]
        for value in values:
            dut.insn.value = encode(op, value if op == "beq" else 5, 3, 2 if op == "beq" else value)
            await settle()
            assert int(dut.immediate.value) == value & MASK
            assert not int(dut.illegal.value)


@cocotb.test()
async def decoder(dut):
    rng = random.Random(34)
    cases = [
        ("add", 1, 1, 1), ("sub", 1, 1, 1), ("addi", 1, 0, 1),
        ("lw", 1, 0, 1), ("sw", 1, 1, 0), ("jal", 0, 0, 1),
        ("jalr", 1, 0, 1), ("lui", 0, 0, 1), ("auipc", 0, 0, 1),
        ("fence", 0, 0, 0), ("ecall", 0, 0, 0), ("ebreak", 0, 0, 0), ("mret", 0, 0, 0),
        *((op, 1, 1, 0) for op in BRANCHES),
        *((op, int(not op.endswith("i")), 0, 1) for op in CSR_OPS),
    ]
    for op, uses_a, uses_b, writes in cases:
        for _ in range(10):
            rd, a, b = (rng.randrange(32) for _ in range(3))
            dut.insn.value = encode(op, rd, a, 0x340 if op in CSR_OPS else b)
            await settle()
            assert (int(dut.uses_rs1.value), int(dut.uses_rs2.value),
                    int(dut.writes_rd.value), int(dut.illegal.value)) == (uses_a, uses_b, writes, 0)
    for word in [0, MASK, 0x02000033, 0x02001013, 0x00003003, 0x00003023, 0x00002063, 0x00004073]:
        dut.insn.value = word
        await settle()
        assert int(dut.illegal.value), hex(word)
