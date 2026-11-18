module rv32i_regfile (
    input  logic clk, reset_n, write_valid,
    input  logic [4:0] rs1, rs2, rd,
    input  logic [31:0] write_data,
    output logic [31:0] read_a, read_b
);
    logic [31:0] registers [1:31];

    always_ff @(posedge clk) begin
        if (!reset_n) begin
            for (int i = 1; i <= 31; i++) registers[i] <= 0;
        end else if (write_valid && rd != 0) begin
            registers[rd] <= write_data;
        end
    end

    assign read_a = rs1 == 0 ? 0 : registers[rs1];
    assign read_b = rs2 == 0 ? 0 : registers[rs2];
endmodule
