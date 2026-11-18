module rv32i_core (
    input  logic clk, reset_n,
    output logic imem_valid,
    output logic [31:0] imem_addr,
    input  logic imem_ready,
    input  logic [31:0] imem_rdata,
    output logic dmem_valid, dmem_write,
    output logic [31:0] dmem_addr, dmem_wdata,
    output logic [3:0] dmem_wstrb,
    input  logic dmem_ready,
    input  logic [31:0] dmem_rdata,
    output logic retire_valid, retire_we,
    output logic [31:0] retire_pc, retire_insn, retire_value,
    output logic [4:0] retire_rd,
    output logic halted
);
    typedef struct packed {
        logic valid;
        logic [31:0] pc, insn;
    } issue_t;

    typedef struct packed {
        logic valid, write_rd, load, store;
        logic [31:0] pc, insn, value, store_data;
    } memory_t;

    typedef struct packed {
        logic valid, write_rd;
        logic [31:0] pc, insn, value;
    } writeback_t;

    logic [31:0] fetch_pc;
    issue_t decode_stage, execute_stage;
    memory_t memory_stage, execute_result;
    writeback_t wb_stage;

    wire execute_valid = execute_stage.valid;
    wire [4:0] rs1 = execute_stage.insn[19:15];
    wire [4:0] rs2 = execute_stage.insn[24:20];
    wire [4:0] ex_rd = execute_stage.insn[11:7];
    wire [4:0] mem_rd = memory_stage.insn[11:7];
    wire [4:0] wb_rd = wb_stage.insn[11:7];

    logic [31:0] reg_a, reg_b, operand_a, operand_b, ex_value;
    logic ex_uses_a, ex_uses_b, ex_writes, ex_trap, ex_mret, ex_load, ex_store;
    logic id_uses_a, id_uses_b, id_unused_write, id_unused_illegal;
    logic [31:0] id_unused_imm;
    logic redirect, csr_illegal;
    logic [31:0] target, load_result, csr_read, trap_pc, return_pc, trap_value;
    logic [3:0] trap_cause;
    wire memory_wait = dmem_valid && !dmem_ready;
    wire trap_taken = execute_valid && ex_trap;

    rv32i_execute execute_op(execute_valid, execute_stage.insn, execute_stage.pc,
                            operand_a, operand_b, csr_illegal, csr_read, return_pc, ex_uses_a, ex_uses_b,
                            ex_writes, ex_trap, ex_mret, ex_load, ex_store, redirect,
                            trap_cause, trap_value, target, ex_value);
    rv32i_machine machine(clk, reset_n, execute_valid && !memory_wait,
                          execute_stage.insn[6:0], execute_stage.insn[14:12], rs1, execute_stage.insn[31:20],
                          execute_stage.pc, operand_a, ex_trap, ex_mret,
                          trap_cause, trap_value, csr_illegal, csr_read, trap_pc, return_pc);
    rv32i_decode decode_id(decode_stage.insn, id_unused_imm, id_uses_a, id_uses_b, id_unused_write, id_unused_illegal);
    rv32i_regfile regfile(clk, reset_n, retire_we, rs1, rs2, wb_rd, wb_stage.value, reg_a, reg_b);

    assign execute_result = {execute_valid && !ex_trap, ex_writes, ex_load, ex_store,
                             execute_stage.pc, execute_stage.insn, ex_value, operand_b};

    wire mem_forward = memory_stage.valid && memory_stage.write_rd && !memory_stage.load && mem_rd != 0;
    wire wb_forward = wb_stage.valid && wb_stage.write_rd && wb_rd != 0;
    wire forward_mem_a = ex_uses_a && mem_forward && rs1 == mem_rd;
    wire forward_mem_b = ex_uses_b && mem_forward && rs2 == mem_rd;
    wire forward_wb_a = ex_uses_a && wb_forward && rs1 == wb_rd && !forward_mem_a;
    wire forward_wb_b = ex_uses_b && wb_forward && rs2 == wb_rd && !forward_mem_b;

    assign operand_a = forward_mem_a ? memory_stage.value : forward_wb_a ? wb_stage.value : reg_a;
    assign operand_b = forward_mem_b ? memory_stage.value : forward_wb_b ? wb_stage.value : reg_b;

    wire load_use = execute_valid && ex_load && ex_rd != 0 && decode_stage.valid &&
                    ((id_uses_a && decode_stage.insn[19:15] == ex_rd) ||
                     (id_uses_b && decode_stage.insn[24:20] == ex_rd));
    wire [1:0] byte_offset = memory_stage.value[1:0];

    assign imem_addr = fetch_pc;
    assign imem_valid = reset_n && !memory_wait && !load_use && !redirect && !trap_taken;
    assign dmem_valid = reset_n && memory_stage.valid && (memory_stage.load || memory_stage.store);
    assign dmem_write = memory_stage.store;
    assign dmem_addr = memory_stage.value;
    rv32i_lsu load_store(memory_stage.insn[14:12], byte_offset, dmem_write,
                         memory_stage.store_data, dmem_rdata, dmem_wdata, load_result, dmem_wstrb);

    assign halted = 1'b0;
    assign retire_valid = reset_n && wb_stage.valid;
    assign retire_pc = wb_stage.pc;
    assign retire_insn = wb_stage.insn;
    assign retire_we = retire_valid && wb_stage.write_rd && wb_rd != 0;
    assign retire_rd = wb_rd;
    assign retire_value = wb_stage.value;

    always_ff @(posedge clk) begin
        if (!reset_n) begin
            fetch_pc <= 0;
            decode_stage <= '0;
            execute_stage <= '0;
            memory_stage <= '0;
            wb_stage <= '0;
        end else begin
            if (memory_wait) begin
                wb_stage.valid <= 0;
            end else begin
                wb_stage.valid <= memory_stage.valid;
                wb_stage.write_rd <= memory_stage.write_rd;
                wb_stage.pc <= memory_stage.pc;
                wb_stage.insn <= memory_stage.insn;
                wb_stage.value <= memory_stage.load ? load_result : memory_stage.value;
                memory_stage <= execute_result;

                if (redirect || trap_taken) begin
                    decode_stage.valid <= 0;
                    execute_stage.valid <= 0;
                    fetch_pc <= trap_taken ? trap_pc : target;
                end else if (load_use) begin
                    execute_stage.valid <= 0;
                end else begin
                    execute_stage <= decode_stage;
                    decode_stage.valid <= imem_valid && imem_ready;
                    if (imem_valid && imem_ready) begin
                        decode_stage.pc <= fetch_pc;
                        decode_stage.insn <= imem_rdata;
                        fetch_pc <= fetch_pc + 4;
                    end
                end
            end
        end
    end

`ifdef FORMAL
    logic past_valid = 0;
    always_ff @(posedge clk) begin
        past_valid <= 1;
        if (!past_valid) assume(!reset_n);
        if (past_valid && reset_n) begin
            assert(fetch_pc[1:0] == 0);
            assert((rs1 != 0 || operand_a == 0) && (rs2 != 0 || operand_b == 0));
            assert(!retire_we || (retire_valid && retire_rd != 0));
            assert((!forward_mem_a || operand_a == memory_stage.value) &&
                   (!forward_mem_b || operand_b == memory_stage.value) &&
                   (!forward_wb_a || operand_a == wb_stage.value) &&
                   (!forward_wb_b || operand_b == wb_stage.value));
            if ($past(reset_n && !memory_wait && (redirect || trap_taken || load_use))) begin
                assert(!execute_stage.valid);
                if ($past(trap_taken)) begin
                    assert(!memory_stage.valid && !decode_stage.valid);
                    assert(fetch_pc == $past(trap_pc));
                end
            end
            if ($past(reset_n && memory_wait)) begin
                assert(dmem_valid && $stable({dmem_addr, dmem_write, dmem_wdata, dmem_wstrb}));
            end
        end
    end
`endif
endmodule
