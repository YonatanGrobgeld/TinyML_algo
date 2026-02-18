`timescale 1ns/1ps

/*
 * Standalone LUT testbench for TinyML softmax/exp lookup table.
 *
 * DUT (in this repo): hw_extensions/exp_lut/exp_lut.v : module exp_lut
 *
 * Goals:
 *  - Verify address-to-data mapping across full LUT range.
 *  - Handle either combinational output or 1-cycle registered output.
 *
 * Expected values are read from expected_lut.mem using $readmemh.
 *
 * TODO (only if needed): If your LUT top module is named differently (lut/softmax_lut),
 * adapt the instantiation and signal names accordingly.
 */

module tb_lut;
  localparam int CLK_PERIOD_NS = 10;
  localparam int LUT_DEPTH     = 16;

  logic clk = 1'b0;
  logic reset = 1'b1;

  logic [4:0] index;
  wire  [15:0] value;

  // Instantiate DUT
  exp_lut dut (
    .clk(clk),
    .reset(reset),
    .index(index),
    .value(value)
  );

  always #(CLK_PERIOD_NS/2) clk = ~clk;

  logic [15:0] exp_ref [0:LUT_DEPTH-1];

  // Latency mode:
  //   0 = combinational (value updates immediately with index)
  //   1 = registered (value corresponds to previous-cycle index)
  //  -1 = auto-detect
  integer latency_mode = -1;

  task automatic cycle();
    @(posedge clk);
  endtask

  task automatic reset_dut();
    index = '0;
    reset = 1'b1;
    repeat (5) cycle();
    reset = 1'b0;
    repeat (2) cycle();
  endtask

  task automatic detect_latency();
    // Simple heuristic: change index and see whether value changes without a clock edge.
    logic [15:0] v0;
    logic [15:0] v1_now;
    index = 5'd0;
    #1;
    v0 = value;
    index = 5'd1;
    #1;
    v1_now = value;

    if (v1_now === exp_ref[1]) begin
      latency_mode = 0;
      $display("TB_LUT: auto-detected combinational output (latency_mode=0)");
    end else begin
      latency_mode = 1;
      $display("TB_LUT: auto-detected registered output (latency_mode=1)");
    end
  endtask

  task automatic check_sweep();
    for (int addr = 0; addr < LUT_DEPTH; addr++) begin
      index = addr[4:0];

      if (latency_mode == 0) begin
        #1; // combinational settle
        if (value !== exp_ref[addr]) begin
          $display("TB_LUT: FAIL sweep addr=%0d dut=0x%04x gold=0x%04x", addr, value, exp_ref[addr]);
          $fatal(1);
        end
      end else begin
        // Registered: drive index, then sample on next cycle (after posedge).
        cycle();
        #1;
        if (value !== exp_ref[addr]) begin
          $display("TB_LUT: FAIL sweep(registered) addr=%0d dut=0x%04x gold=0x%04x", addr, value, exp_ref[addr]);
          $fatal(1);
        end
      end
    end
  endtask

  initial begin
    $dumpfile("tb_lut.vcd");
    $dumpvars(0, tb_lut);

    // Load expected LUT values.
    // expected_lut.mem format: 1 hex value per line (16-bit), addresses 0..15.
    $readmemh("expected_lut.mem", exp_ref);

    reset_dut();

    if (latency_mode < 0) begin
      detect_latency();
    end

    // Sweep full LUT range.
    check_sweep();

    // Optional sanity: demonstrate signed index behavior.
    // NOTE: current RTL maps addr = index[3:0]. A true signed mapping (0,-1..-15) would need logic.
    // TODO: If the intended interface is signed 0,-1..-15, update RTL or add a signed-to-addr mapping,
    // then extend this TB to verify that mapping explicitly.
    index = 5'b11111; // -1 in 5-bit two's complement
    #1;
    $display("TB_LUT: NOTE index=-1 (0x1f) produces value=0x%04x (addr=index[3:0]=15).", value);

    $display("TB_LUT: ALL TESTS PASS");
    $finish;
  end

endmodule

