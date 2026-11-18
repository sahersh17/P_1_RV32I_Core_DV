OUTPUT_ARCH(riscv)
ENTRY(rvtest_entry_point)

SECTIONS {
  . = 0x80000000;
  .text : { KEEP(*(.text.init)) *(.text .text.*) }
  . = ALIGN(16);
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.* .sdata .sdata.*) }
  .tohost : { KEEP(*(.tohost)) }
  .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
}
