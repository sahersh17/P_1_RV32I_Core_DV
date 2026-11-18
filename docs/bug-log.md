# Verification bug log

| Symptom | Root cause | Fix and regression |
| --- | --- | --- |
| ECALL, EBREAK, illegal instructions and misaligned accesses ended the simulation | The execute stage used a shared halt path instead of recording an architectural exception | Both cores now enter the machine trap vector, record the cause and fault address, and support MRET. The directed suite checks every implemented cause and compares the handler's register writes. |
| A fault was reported as a retired instruction | The original halt marker shared the normal retirement stream | A faulting instruction now leaves the retirement stream empty. Directed tests check that it issues no data request, younger stores are squashed, and an older store completes under memory backpressure. |
| Embedded programs linked at the machine memory base could not be loaded directly | Both RTL tops fixed reset at address zero | The word-aligned reset vector defaults to zero and can be set by an integration. The ELF harness sets it to 0x80000000 and drives the instruction and data ports from the loaded image. |
