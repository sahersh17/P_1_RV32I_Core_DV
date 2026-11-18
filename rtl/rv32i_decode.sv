module rv32i_decode (
    input  logic [31:0] insn,
    output logic [31:0] immediate,
    output logic uses_rs1, uses_rs2, writes_rd, illegal
);
    wire [2:0] funct3 = insn[14:12];
    wire [6:0] funct7 = insn[31:25];

    always @* begin
        immediate = {{20{insn[31]}}, insn[31:20]};
        uses_rs1 = 0;
        uses_rs2 = 0;
        writes_rd = 0;
        illegal = 0;
        case (insn[6:0])
            7'h37, 7'h17: begin
                immediate = {insn[31:12], 12'b0};
                writes_rd = 1;
            end
            7'h6f: begin
                immediate = {{12{insn[31]}}, insn[19:12], insn[20], insn[30:21], 1'b0};
                writes_rd = 1;
            end
            7'h67: begin
                uses_rs1 = 1;
                writes_rd = 1;
                illegal = funct3 != 0;
            end
            7'h63: begin
                immediate = {{20{insn[31]}}, insn[7], insn[30:25], insn[11:8], 1'b0};
                uses_rs1 = 1;
                uses_rs2 = 1;
                illegal = funct3 == 2 || funct3 == 3;
            end
            7'h03: begin
                uses_rs1 = 1;
                writes_rd = 1;
                illegal = funct3 == 3 || funct3 > 5;
            end
            7'h23: begin
                immediate = {{20{insn[31]}}, insn[31:25], insn[11:7]};
                uses_rs1 = 1;
                uses_rs2 = 1;
                illegal = funct3 > 2;
            end
            7'h13: begin
                uses_rs1 = 1;
                writes_rd = 1;
                if (funct3 == 1) illegal = funct7 != 0;
                if (funct3 == 5) illegal = funct7 != 0 && funct7 != 7'h20;
            end
            7'h33: begin
                uses_rs1 = 1;
                uses_rs2 = 1;
                writes_rd = 1;
                illegal = funct7 != 0 && !(funct7 == 7'h20 && (funct3 == 0 || funct3 == 5));
            end
            7'h0f: illegal = funct3 != 0;
            7'h73: illegal = insn != 32'h00000073 && insn != 32'h00100073;
            default: illegal = 1;
        endcase
    end
endmodule
