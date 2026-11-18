module rv32i_single_cycle (
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
    logic [31:0] pc, pending_insn;
    logic pending;
    logic [31:0] a, b, target, result, loaded_value;
    logic unused_rs1, unused_rs2, writes, halt, load, store, redirect;
    wire issue = reset_n && !halted && (pending || imem_ready);

    assign imem_addr = pc;
    assign imem_valid = reset_n && !halted && !pending;
    assign retire_pc = pc;
    assign retire_insn = pending ? pending_insn : imem_rdata;

    rv32i_regfile regfile(clk, reset_n, retire_we, retire_insn[19:15], retire_insn[24:20],
                          retire_rd, retire_value, a, b);
    rv32i_execute execute_op(issue, retire_insn, pc, a, b,
                            unused_rs1, unused_rs2, writes, halt, load, store, redirect, target, result);
    rv32i_lsu load_store(retire_insn[14:12], result[1:0], store,
                         b, dmem_rdata, dmem_wdata, loaded_value, dmem_wstrb);

    assign dmem_valid = issue && (load || store);
    assign dmem_addr = result;
    assign dmem_write = store;
    assign retire_valid = issue && (!dmem_valid || dmem_ready);
    assign retire_rd = retire_insn[11:7];
    assign retire_we = retire_valid && writes && retire_rd != 0;
    assign retire_value = load ? loaded_value : result;

    always_ff @(posedge clk) begin
        if (!reset_n) begin
            pc <= 0;
            pending <= 0;
            pending_insn <= 0;
            halted <= 0;
        end else if (retire_valid) begin
            pending <= 0;
            if (halt) halted <= 1;
            else pc <= redirect ? target : pc + 4;
        end else if (imem_valid && imem_ready) begin
            pending <= 1;
            pending_insn <= imem_rdata;
        end
    end
endmodule
