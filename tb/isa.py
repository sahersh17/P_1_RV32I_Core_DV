"""Instruction encoding and an instruction-at-a-time reference model."""

MASK = (1 << 32) - 1
R_OPS = ("add", "sll", "slt", "sltu", "xor", "srl", "or", "and")
I_OPS = ("addi", "slli", "slti", "sltiu", "xori", "srli", "ori", "andi")
LOADS = {"lb": (0, 1), "lh": (1, 2), "lw": (2, 4), "lbu": (4, 1), "lhu": (5, 2)}
STORES = {"sb": 1, "sh": 2, "sw": 4}
BRANCHES = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}
SYSTEM = {"fence": 0x0FF0000F, "ecall": 0x73, "ebreak": 0x100073, "illegal": MASK}


def sx(value, bits):
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def encode(op, rd, a, b):
    # For stores rd denotes rs2. For branches rd is the byte displacement.
    if op in R_OPS or op in ("sub", "sra"):
        f3 = {"sub": 0, "sra": 5}[op] if op in ("sub", "sra") else R_OPS.index(op)
        return ((op in ("sub", "sra")) << 30) | b << 20 | a << 15 | f3 << 12 | rd << 7 | 0x33
    if op in I_OPS or op == "srai":
        f3 = 5 if op == "srai" else I_OPS.index(op)
        imm = (b & 0xFFF) | (0x400 if op == "srai" else 0)
        return imm << 20 | a << 15 | f3 << 12 | rd << 7 | 0x13
    if op in LOADS or op == "jalr":
        f3 = LOADS[op][0] if op in LOADS else 0
        return (b & 0xFFF) << 20 | a << 15 | f3 << 12 | rd << 7 | (0x67 if op == "jalr" else 3)
    if op in STORES:
        imm = b & 0xFFF
        return imm >> 5 << 25 | rd << 20 | a << 15 | (STORES[op].bit_length() - 1) << 12 | (imm & 31) << 7 | 0x23
    if op in BRANCHES:
        return ((rd >> 12 & 1) << 31 | (rd >> 5 & 63) << 25 | b << 20 | a << 15 |
                BRANCHES[op] << 12 | (rd >> 1 & 15) << 8 | (rd >> 11 & 1) << 7 | 0x63)
    if op == "jal":
        return ((b >> 20 & 1) << 31 | (b >> 1 & 1023) << 21 | (b >> 11 & 1) << 20 |
                (b >> 12 & 255) << 12 | rd << 7 | 0x6F)
    if op in ("lui", "auipc"):
        return b & 0xFFFFF000 | rd << 7 | (0x37 if op == "lui" else 0x17)
    return SYSTEM[op]


def reference(program):
    regs = [0] * 32
    data = bytearray(1024)
    events = []
    covered = set()
    pc = 0
    for _ in range(1000):
        op, rd, a, b = program[pc // 4]
        covered.add(op)
        left = regs[a]
        target = pc + 4
        value = None
        halt = op in ("ecall", "ebreak", "illegal")
        if op in ("lui", "auipc"):
            value = b + (pc if op == "auipc" else 0)
        elif op in ("jal", "jalr"):
            target = pc + b if op == "jal" else ((left + b) & MASK) & ~1
            value = pc + 4
        elif op in BRANCHES:
            right = regs[b]
            taken = {
                "beq": left == right, "bne": left != right,
                "blt": sx(left, 32) < sx(right, 32),
                "bge": sx(left, 32) >= sx(right, 32),
                "bltu": left < right, "bgeu": left >= right,
            }[op]
            if taken:
                target = pc + rd
        elif op in LOADS or op in STORES:
            addr = (left + b) & MASK
            size = LOADS[op][1] if op in LOADS else STORES[op]
            halt = addr % size != 0
            if not halt and op in LOADS:
                value = int.from_bytes(data[addr:addr + size], "little", signed=op in ("lb", "lh", "lw"))
            elif not halt:
                stored = regs[rd] & ((1 << (size * 8)) - 1)
                data[addr:addr + size] = stored.to_bytes(size, "little")
                events.append(("STORE", addr, ((1 << size) - 1) << (addr % 4),
                               (regs[rd] << (8 * (addr % 4))) & MASK))
        elif op != "fence" and not halt:
            immediate = op in I_OPS or op == "srai"
            right = (b & MASK) if immediate else regs[b]
            kind = "sltu" if op == "sltiu" else op.removesuffix("i")
            shift = right % 32
            value = {
                "add": left + right, "sub": left - right, "sll": left << shift,
                "slt": int(sx(left, 32) < sx(right, 32)), "sltu": int(left < right),
                "xor": left ^ right, "srl": left >> shift, "sra": sx(left, 32) >> shift,
                "or": left | right, "and": left & right,
            }[kind]
        halt |= bool(target % 4)
        written = rd if value is not None and not halt else 0
        if written:
            regs[written] = value & MASK
        events.append(("RETIRE", pc, encode(op, rd, a, b), written, regs[written]))
        if halt:
            return events, covered
        pc = target
    raise ValueError("Reference program did not halt")
