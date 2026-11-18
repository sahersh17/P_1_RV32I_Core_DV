OUTPUT_ARCH(riscv)
ENTRY(rvtest_entry_point)

PHDRS { image PT_LOAD FLAGS(7); }

SECTIONS {
  . = 0x80000000;
  .text : { KEEP(*(.text.init)) *(.text .text.*) } :image
  . = ALIGN(16);
  .rodata : { *(.rodata .rodata.*) } :image
  .data : { *(.data .data.* .sdata .sdata.*) } :image
  .tohost : { KEEP(*(.tohost)) } :image
  .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) } :image
}
