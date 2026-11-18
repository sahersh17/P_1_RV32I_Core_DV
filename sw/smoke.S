#include "model_test.h"

.section .text.init
.global rvtest_entry_point
rvtest_entry_point:
    la t0, vector
    csrw mtvec, t0
    li t0, 10
    li t1, 0
1:  add t1, t1, t0
    addi t0, t0, -1
    bnez t0, 1b

    la t2, begin_signature
    sw t1, 0(t2)
    lw t3, 0(t2)
    addi t3, t3, 1
    sw t3, 4(t2)
    ecall
    RVMODEL_HALT

.balign 4
vector:
    csrr t4, mcause
    sw t4, 8(t2)
    csrr t4, mepc
    addi t4, t4, 4
    csrw mepc, t4
    mret

.section .data
RVMODEL_DATA_BEGIN
    .word 0, 0, 0
RVMODEL_DATA_END
