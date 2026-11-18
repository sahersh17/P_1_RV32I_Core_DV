"""Instruction encoding and an instruction-at-a-time reference model."""

MASK = (1 << 32) - 1
R_OPS = ("add", "sll", "slt", "sltu", "xor", "srl", "or", "and")
I_OPS = ("addi", "slli", "slti", "sltiu", "xori", "srli", "ori", "andi")
LOADS = {"lb": (0, 1), "lh": (1, 2), "lw": (2, 4), "lbu": (4, 1), "lhu": (5, 2)}
STORES = {"sb": 1, "sh": 2, "sw": 4}
BRANCHES = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}
SYSTEM = {"fence": 0x0FF0000F, "ecall": 0x73, "ebreak": 0x100073, "mret": 0x30200073, "illegal": MASK}
CSR_OPS = {"csrrw": 1, "csrrs": 2, "csrrc": 3, "csrrwi": 5, "csrrsi": 6, "csrrci": 7}
COMPLETION = ("sw", 0, 0, 1020)
MSTATUS, MTVEC, MSCRATCH, MEPC, MCAUSE, MTVAL = 0x300, 0x305, 0x340, 0x341, 0x342, 0x343
MSTATUS_FIXED = 3 << 11
CSR_FIXED = {0x301: 0x40000100, **dict.fromkeys((0x304, 0x310, 0x344, 0xF11, 0xF12, 0xF13, 0xF14), 0)}


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
    if op in CSR_OPS:
        return b << 20 | a << 15 | CSR_OPS[op] << 12 | rd << 7 | 0x73
    return SYSTEM[op]


def reference(program):
    regs = [0] * 32
    data = bytearray(1024)
    events = []
    covered = set()
    csr = dict.fromkeys((MTVEC, MSCRATCH, MEPC, MCAUSE, MTVAL), 0)
    csr[MSTATUS] = MSTATUS_FIXED
    pc = 0
    for _ in range(1000):
        instruction = program[pc // 4]
        op, rd, a, b = instruction
        word = encode(*instruction)
        covered.add(op)
        left = regs[a]
        target = pc + 4
        value = None
        cause = None
        fault_value = 0
        if op == "ecall":
            cause = 11
        elif op == "ebreak":
            cause, fault_value = 3, pc
        elif op == "illegal":
            cause, fault_value = 2, word
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
            if addr % size:
                cause, fault_value = (4 if op in LOADS else 6), addr
            elif op in LOADS:
                events.append(("LOAD", addr))
                value = int.from_bytes(data[addr:addr + size], "little", signed=op in ("lb", "lh", "lw"))
            else:
                stored = regs[rd] & ((1 << (size * 8)) - 1)
                data[addr:addr + size] = stored.to_bytes(size, "little")
                events.append(("STORE", addr, ((1 << size) - 1) << (addr % 4),
                               (regs[rd] << (8 * (addr % 4))) & MASK))
        elif op in CSR_OPS:
            source = a if op.endswith("i") else left
            write = op in ("csrrw", "csrrwi") or a != 0
            if b not in csr and b not in CSR_FIXED or write and b >> 10 == 3:
                cause, fault_value = 2, word
            else:
                value = csr.get(b, CSR_FIXED.get(b))
                if write and b in csr:
                    if op in ("csrrs", "csrrsi"):
                        source |= value
                    elif op in ("csrrc", "csrrci"):
                        source = value & ~source
                    if b in (MTVEC, MEPC):
                        source &= ~3
                    elif b == MSTATUS:
                        source = MSTATUS_FIXED | (source & 0x88)
                    csr[b] = source
        elif op == "mret":
            target = csr[MEPC]
            csr[MSTATUS] = MSTATUS_FIXED | 0x80 | ((csr[MSTATUS] & 0x80) >> 4)
        elif op != "fence" and cause is None:
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
        if target % 4:
            cause, fault_value = 0, target & MASK
        if cause is not None:
            csr[MEPC], csr[MCAUSE], csr[MTVAL] = pc, cause, fault_value
            csr[MSTATUS] = MSTATUS_FIXED | ((csr[MSTATUS] & 8) << 4)
            pc = csr[MTVEC]
            continue
        written = rd if value is not None else 0
        if written:
            regs[written] = value & MASK
        events.append(("RETIRE", pc, word, written, regs[written]))
        if instruction == COMPLETION:
            return events, covered
        pc = target
    raise ValueError("Reference program did not reach the completion store")
