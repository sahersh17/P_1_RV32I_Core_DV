"""Load the bare-metal RV32 ELF format used by the simulator harness."""

from elftools.elf.elffile import ELFFile

BASE = 0x80000000
SIZE = 0x400000


def load_elf(path):
    with open(path, "rb") as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 32 or not elf.little_endian or elf["e_machine"] != "EM_RISCV":
            raise ValueError(f"{path}: expected a little-endian ELF32 RISC-V image")
        if elf["e_entry"] != BASE:
            raise ValueError(f"{path}: entry point must be {BASE:#x}")
        memory = bytearray(SIZE)
        for segment in elf.iter_segments(type="PT_LOAD"):
            addr, physical = segment["p_vaddr"], segment["p_paddr"]
            size, data = segment["p_memsz"], segment.data()
            if addr != physical or addr < BASE or addr + size > BASE + SIZE or len(data) > size:
                raise ValueError(f"{path}: incompatible load segment at {addr:#x}")
            memory[addr - BASE:addr - BASE + len(data)] = data
        table = elf.get_section_by_name(".symtab")
        if table is None:
            raise ValueError(f"{path}: symbol table required")
        symbols = {sym.name: sym["st_value"] for sym in table.iter_symbols()}
    start, end, tohost = (symbols[name] for name in ("begin_signature", "end_signature", "tohost"))
    if (start % 4 or end % 4 or tohost % 4 or not BASE <= start < end <= BASE + SIZE
            or not BASE <= tohost <= BASE + SIZE - 4):
        raise ValueError(f"{path}: incompatible signature or tohost location")
    return memory, start, end, tohost
