#ifndef RV32I_MODEL_TEST_H
#define RV32I_MODEL_TEST_H

#define RVMODEL_BOOT
#define RVMODEL_HALT                 \
    li t0, 1;                        \
    la t1, tohost;                   \
    sw t0, 0(t1);                    \
1:  j 1b

#define RVMODEL_DATA_BEGIN           \
    .balign 16;                      \
    .global begin_signature;        \
begin_signature:

#define RVMODEL_DATA_END             \
    .balign 16;                      \
    .global end_signature;          \
end_signature:                      \
    .pushsection .tohost,"aw",@progbits; \
    .balign 64;                      \
    .global tohost;                  \
tohost: .dword 0;                    \
    .balign 64;                      \
    .global fromhost;                \
fromhost: .dword 0;                  \
    .popsection

#define RVMODEL_IO_INIT
#define RVMODEL_IO_WRITE_STR(...)
#define RVMODEL_IO_CHECK(...)
#define RVMODEL_IO_ASSERT_GPR_EQ(...)
#define RVMODEL_IO_ASSERT_SFPR_EQ(...)
#define RVMODEL_IO_ASSERT_DFPR_EQ(...)

#endif
