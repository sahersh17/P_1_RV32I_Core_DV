module rv32i_lsu (
    input  logic [2:0] funct3,
    input  logic [1:0] byte_offset,
    input  logic write,
    input  logic [31:0] store_data, read_data,
    output logic [31:0] write_data, load_value,
    output logic [3:0] write_strobe
);
    logic [7:0] load_byte;
    logic [15:0] load_half;

    assign write_data = store_data << (8 * byte_offset);
    always @* begin
        case (funct3[1:0])
            2'b00: write_strobe = 4'b0001 << byte_offset;
            2'b01: write_strobe = 4'b0011 << byte_offset;
            default: write_strobe = 4'b1111;
        endcase
        if (!write) write_strobe = 0;
    end

    assign load_byte = read_data[8 * byte_offset +: 8];
    assign load_half = read_data[16 * byte_offset[1] +: 16];
    always @* begin
        case (funct3)
            3'b000: load_value = {{24{load_byte[7]}}, load_byte};
            3'b001: load_value = {{16{load_half[15]}}, load_half};
            3'b100: load_value = {24'b0, load_byte};
            3'b101: load_value = {16'b0, load_half};
            default: load_value = read_data;
        endcase
    end

endmodule
