module rv32i_machine (
    input  logic clk, reset_n, advance,
    input  logic [6:0] opcode,
    input  logic [2:0] op,
    input  logic [4:0] rs1,
    input  logic [11:0] csr,
    input  logic [31:0] pc, operand,
    input  logic trap, mret,
    input  logic [3:0] cause,
    input  logic [31:0] trap_value,
    output logic csr_illegal,
    output logic [31:0] csr_read, trap_pc, return_pc
);
    logic mie, mpie;
    logic [31:0] mtvec, mscratch, mepc, mcause, mtval;
    wire csr_access = opcode == 7'h73 && op != 0 && op != 4;
    wire csr_write = op[1:0] == 1 || rs1 != 0;
    wire [31:0] source = op[2] ? {27'b0, rs1} : operand;
    logic implemented;
    logic [31:0] write_value;

    assign trap_pc = mtvec;
    assign return_pc = mepc;

    always @* begin
        implemented = 1;
        csr_read = 0;
        case (csr)
            12'h300: csr_read = {19'b0, 2'b11, 3'b0, mpie, 3'b0, mie, 3'b0};
            12'h301: csr_read = 32'h40000100;
            12'h304, 12'h310, 12'h344, 12'hf11, 12'hf12, 12'hf13, 12'hf14: csr_read = 0;
            12'h305: csr_read = mtvec;
            12'h340: csr_read = mscratch;
            12'h341: csr_read = mepc;
            12'h342: csr_read = mcause;
            12'h343: csr_read = mtval;
            default: implemented = 0;
        endcase
    end

    assign csr_illegal = csr_access && (!implemented || (csr[11:10] == 2'b11 && csr_write));

    always @* begin
        case (op[1:0])
            2'd2: write_value = csr_read | source;
            2'd3: write_value = csr_read & ~source;
            default: write_value = source;
        endcase
    end

    always_ff @(posedge clk) begin
        if (!reset_n) begin
            mie <= 0;
            mpie <= 0;
            mtvec <= 0;
            mscratch <= 0;
            mepc <= 0;
            mcause <= 0;
            mtval <= 0;
        end else if (advance) begin
            if (trap) begin
                mepc <= pc;
                mcause <= {28'b0, cause};
                mtval <= trap_value;
                mpie <= mie;
                mie <= 0;
            end else if (mret) begin
                mie <= mpie;
                mpie <= 1;
            end else if (csr_access && csr_write) begin
                case (csr)
                    12'h300: begin
                        mie <= write_value[3];
                        mpie <= write_value[7];
                    end
                    12'h305: mtvec <= {write_value[31:2], 2'b00};
                    12'h340: mscratch <= write_value;
                    12'h341: mepc <= {write_value[31:2], 2'b00};
                    12'h342: mcause <= write_value;
                    12'h343: mtval <= write_value;
                    default: begin end
                endcase
            end
        end
    end
endmodule
