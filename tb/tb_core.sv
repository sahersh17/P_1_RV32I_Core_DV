module tb_core;
    logic clk = 0, reset_n = 0;
    always #5 clk = ~clk;

    wire imem_valid, dmem_valid, dmem_write, retire_valid, retire_we, halted;
    wire [31:0] imem_addr, dmem_addr, dmem_wdata, retire_pc, retire_insn, retire_value;
    wire [3:0] dmem_wstrb;
    wire [4:0] retire_rd;
    logic [31:0] rom [0:255];
    logic [31:0] ram [0:255];
    integer cycle = 0, count, test_id;
    bit wait_states, completed;
    localparam logic [31:0] COMPLETION_STORE = 32'h3e002e23;
    logic [9:0] coverage_bits = 0;
    wire imem_ready = !wait_states || cycle % 7 != 2;
    wire dmem_ready = !wait_states || cycle % 5 == 0;
    wire [31:0] imem_rdata = imem_addr < 1024 ? rom[imem_addr[9:2]] : 0;
    wire [31:0] dmem_rdata = dmem_addr < 1024 ? ram[dmem_addr[9:2]] : 0;
`ifdef SINGLE_CYCLE
    rv32i_single_cycle dut(.*);
`else
    rv32i_core dut(.*);
`endif

    always @(posedge clk) if (reset_n) begin
        cycle <= cycle + 1;
        if (dmem_valid && dmem_ready) begin
            if (dmem_addr >= 1024) $fatal(1, "Out-of-range data address %h", dmem_addr);
            if (dmem_write) begin
                $display("STORE %h %h %h", dmem_addr, dmem_wstrb, dmem_wdata);
                for (integer b = 0; b < 4; b++)
                    if (dmem_wstrb[b])
                        ram[dmem_addr[9:2]][8*b +: 8] <= dmem_wdata[8*b +: 8];
            end else $display("LOAD %h", dmem_addr);
        end
        if (halted) $fatal(1, "Core halted instead of taking a trap");
        if (retire_valid)
            $display("RETIRE %h %h %0d %h", retire_pc, retire_insn,
                     retire_we ? retire_rd : 5'b0, retire_we ? retire_value : 32'b0);
`ifndef SINGLE_CYCLE
        if (!dut.memory_wait && dut.execute_valid) begin
            coverage_bits[0] <= coverage_bits[0] || dut.forward_mem_a;
            coverage_bits[1] <= coverage_bits[1] || dut.forward_mem_b;
            coverage_bits[2] <= coverage_bits[2] || dut.forward_wb_a;
            coverage_bits[3] <= coverage_bits[3] || dut.forward_wb_b;
            coverage_bits[4] <= coverage_bits[4] || dut.load_use;
            coverage_bits[5] <= coverage_bits[5] || (dut.execute_op.opcode == 7'h63 && dut.redirect);
            coverage_bits[6] <= coverage_bits[6] || (dut.execute_op.opcode == 7'h63 && !dut.redirect);
            coverage_bits[9] <= coverage_bits[9] || (dut.forward_mem_a && dut.forward_wb_b);
        end
        coverage_bits[7] <= coverage_bits[7] || dut.memory_wait;
        coverage_bits[8] <= coverage_bits[8] || (imem_valid && !imem_ready);
`endif
    end

    always @(posedge clk)
        if (!reset_n) completed <= 0;
        else if (retire_valid && retire_insn == COMPLETION_STORE) completed <= 1;

    initial begin
        if (!$value$plusargs("cases=%d", count)) $fatal(1, "Specify +cases=N");
        if ($test$plusargs("waves")) begin
            $dumpfile("core.vcd");
            $dumpvars(0, dut);
        end
        for (test_id = 0; test_id < count; test_id++) begin
            reset_n = 0;
            wait_states = test_id % 2 != 0;
            $display("CASE %0d", test_id);
            $readmemh($sformatf("case%04d.hex", test_id), rom);
            for (integer w = 0; w < 256; w++) ram[w] = 0;
            repeat (2) @(negedge clk);
            reset_n = 1;
            for (integer c = 0; !completed && c < 1800; c++) @(negedge clk);
            if (!completed) $fatal(1, "Case %0d timed out", test_id);
        end
        $display("COVERAGE %h", coverage_bits);
        $finish;
    end
endmodule
