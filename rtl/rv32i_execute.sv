module rv32i_execute (
    input  logic valid,
    input  logic [31:0] insn, pc, operand_a, operand_b,
    output logic uses_a, uses_b, write_rd, halt, load, store, redirect,
    output logic [31:0] target, value
);
    wire [6:0] opcode = insn[6:0];
    wire [2:0] funct3 = insn[14:12];
    logic [31:0] immediate, alu_b, alu_result;
    logic decoded_write, illegal, branch_taken;

    rv32i_decode decode_op(insn, immediate, uses_a, uses_b, decoded_write, illegal);
    assign alu_b = opcode == 7'h33 ? operand_b : immediate;
    rv32i_alu alu(funct3, insn[30] && (opcode == 7'h33 || funct3 == 5),
                  operand_a, alu_b, alu_result);

    always @* begin
        case (funct3)
            3'b000: branch_taken = operand_a == operand_b;
            3'b001: branch_taken = operand_a != operand_b;
            3'b100: branch_taken = $signed(operand_a) < $signed(operand_b);
            3'b101: branch_taken = $signed(operand_a) >= $signed(operand_b);
            3'b110: branch_taken = operand_a < operand_b;
            3'b111: branch_taken = operand_a >= operand_b;
            default: branch_taken = 0;
        endcase
    end

    always @* begin
        write_rd = decoded_write;
        halt = 0;
        load = 0;
        store = 0;
        value = alu_result;
        redirect = 0;
        target = pc + immediate;
        case (opcode)
            7'h37: value = immediate;
            7'h17: value = target;
            7'h6f, 7'h67: begin
                value = pc + 4;
                if (opcode == 7'h67) target = (operand_a + immediate) & 32'hfffffffe;
                redirect = 1;
            end
            7'h63: redirect = branch_taken;
            7'h03, 7'h23: begin
                value = operand_a + immediate;
                load = opcode == 7'h03;
                store = opcode == 7'h23;
                case (funct3[1:0])
                    2'b01: halt = value[0];
                    2'b10: halt = value[1:0] != 0;
                    default: halt = 0;
                endcase
            end
            7'h73: halt = 1;
            default: begin end
        endcase
        if (illegal || halt || (redirect && target[1:0] != 0)) begin
            halt = 1;
            write_rd = 0;
            load = 0;
            store = 0;
            redirect = 0;
        end
        redirect = redirect && valid;
    end

endmodule
