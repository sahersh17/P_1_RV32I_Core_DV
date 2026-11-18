module rv32i_alu (
    input  logic [2:0]  operation,
    input  logic        alternate,
    input  logic [31:0] a, b,
    output logic [31:0] result
);
    always @* begin
        case (operation)
            3'b000: result = alternate ? a - b : a + b;
            3'b001: result = a << b[4:0];
            3'b010: result = {31'b0, $signed(a) < $signed(b)};
            3'b011: result = {31'b0, a < b};
            3'b100: result = a ^ b;
            3'b101: begin
                if (alternate) result = $unsigned($signed(a) >>> b[4:0]);
                else result = a >> b[4:0];
            end
            3'b110: result = a | b;
            3'b111: result = a & b;
            default: result = 0;
        endcase
    end
endmodule
