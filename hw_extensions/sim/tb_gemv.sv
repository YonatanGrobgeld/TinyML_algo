`timescale 1ns/1ps

/*
 * Standalone GEMV testbench for TinyML GEMV core.
 *
 * DUT (in this repo): hw_extensions/gemv/rtl/gemv_core.v : module gemv_core
 *
 * Computes: Y = W*X + b (optional), with signed int8 W/X and signed int32 b/Y.
 * Dimensions are configured by len_64/out_dim_64: {32,64} each.
 *
 * This TB uses LEN=32 and OUT_DIM=32 (len_64=0, out_dim_64=0) and tests:
 *  - 1 deterministic test
 *  - 1 randomized test (fixed seed)
 *  - 1 boundary/extremes test (min/max int8)
 *
 * Note: If your top-level GEMV module is named `gemv` or `gemv16` with different ports,
 * add a small adapter wrapper and map to the gemv_core-style signals. (TODO in that case.)
 */

module tb_gemv;
  localparam int CLK_PERIOD_NS = 10;
  localparam int LEN           = 32;
  localparam int OUT_DIM       = 32;
  localparam int ACTIVE_N      = 16; // We load only first 16 cols with data; remaining are 0.
  localparam int ACTIVE_M      = 4;  // We check first 4 rows; remaining rows are 0.

  // Clock/reset
  logic clk = 1'b0;
  logic reset = 1'b1;

  // DUT ports (gemv_core)
  logic        x_wr_en;
  logic [7:0]  x_wr_data;
  logic        w_wr_en;
  logic [7:0]  w_wr_data;
  logic        b_wr_en;
  logic [31:0] b_wr_data;

  logic start;
  logic len_64;
  logic out_dim_64;
  logic bias_en;
  logic clear_done;

  logic busy;
  logic done;

  logic        y_rd_en;
  wire [31:0]  y_rd_data;

  // Instantiate DUT
  gemv_core dut (
    .clk(clk),
    .reset(reset),
    .x_wr_en(x_wr_en),
    .x_wr_data(x_wr_data),
    .w_wr_en(w_wr_en),
    .w_wr_data(w_wr_data),
    .b_wr_en(b_wr_en),
    .b_wr_data(b_wr_data),
    .start(start),
    .len_64(len_64),
    .out_dim_64(out_dim_64),
    .bias_en(bias_en),
    .busy(busy),
    .done(done),
    .clear_done(clear_done),
    .y_rd_en(y_rd_en),
    .y_rd_data(y_rd_data)
  );

  // Clock generation
  always #(CLK_PERIOD_NS/2) clk = ~clk;

  // -----------------------
  // Helpers / reference
  // -----------------------
  typedef byte signed i8_t;
  typedef int  signed i32_t;

  i8_t x_ref   [0:LEN-1];
  i8_t w_ref   [0:OUT_DIM-1][0:LEN-1];
  i32_t b_ref  [0:OUT_DIM-1];
  i32_t y_gold [0:OUT_DIM-1];

  task automatic cycle();
    @(posedge clk);
  endtask

  task automatic reset_dut();
    x_wr_en     = 1'b0;
    x_wr_data   = '0;
    w_wr_en     = 1'b0;
    w_wr_data   = '0;
    b_wr_en     = 1'b0;
    b_wr_data   = '0;
    start       = 1'b0;
    len_64      = 1'b0;
    out_dim_64  = 1'b0;
    bias_en     = 1'b0;
    clear_done  = 1'b0;
    y_rd_en     = 1'b0;

    reset = 1'b1;
    repeat (5) cycle();
    reset = 1'b0;
    repeat (2) cycle();
  endtask

  task automatic pulse_clear_done();
    clear_done = 1'b1;
    cycle();
    clear_done = 1'b0;
    cycle();
  endtask

  task automatic pulse_start();
    start = 1'b1;
    cycle();
    start = 1'b0;
  endtask

  task automatic load_x();
    // Assumes clear_done was pulsed so x write index is 0.
    for (int c = 0; c < LEN; c++) begin
      x_wr_data = x_ref[c];
      x_wr_en   = 1'b1;
      cycle();
      x_wr_en   = 1'b0;
      cycle();
    end
  endtask

  task automatic load_w();
    // Assumes clear_done was pulsed so w write index is 0. Row-major OUT_DIM x LEN.
    for (int r = 0; r < OUT_DIM; r++) begin
      for (int c = 0; c < LEN; c++) begin
        w_wr_data = w_ref[r][c];
        w_wr_en   = 1'b1;
        cycle();
        w_wr_en   = 1'b0;
        cycle();
      end
    end
  endtask

  task automatic load_b();
    // Assumes clear_done was pulsed so b write index is 0. OUT_DIM entries.
    for (int r = 0; r < OUT_DIM; r++) begin
      b_wr_data = b_ref[r];
      b_wr_en   = 1'b1;
      cycle();
      b_wr_en   = 1'b0;
      cycle();
    end
  endtask

  task automatic compute_golden();
    for (int r = 0; r < OUT_DIM; r++) begin
      i32_t acc = (bias_en) ? b_ref[r] : 0;
      for (int c = 0; c < LEN; c++) begin
        acc += i32_t'(x_ref[c]) * i32_t'(w_ref[r][c]);
      end
      y_gold[r] = acc;
    end
  endtask

  task automatic wait_done_with_timeout(input int max_cycles);
    int cyc = 0;
    // The core sets busy when start is accepted; done becomes 1 in DONE state.
    while (done !== 1'b1) begin
      cycle();
      cyc++;
      if (cyc > max_cycles) begin
        $display("TB_GEMV: TIMEOUT waiting for done after %0d cycles (busy=%0b done=%0b)", cyc, busy, done);
        $fatal(1);
      end
    end
  endtask

  task automatic read_and_check_y(input string name);
    // y_rd_data is combinational for current y_rd_idx; y_rd_idx increments on y_rd_en pulse.
    // We pulse clear_done before starting each test to reset y_rd_idx to 0.
    i32_t y_dut;
    for (int r = 0; r < OUT_DIM; r++) begin
      #1; // allow combinational settle
      y_dut = i32_t'($signed(y_rd_data));
      if (y_dut !== y_gold[r]) begin
        $display("TB_GEMV: FAIL (%s) row=%0d  dut=%0d (0x%08x)  gold=%0d (0x%08x)",
                 name, r, y_dut, y_dut, y_gold[r], y_gold[r]);
        $fatal(1);
      end
      // Advance to next output
      y_rd_en = 1'b1;
      cycle();
      y_rd_en = 1'b0;
      cycle();
    end
  endtask

  task automatic init_zero_all();
    for (int c = 0; c < LEN; c++) x_ref[c] = 0;
    for (int r = 0; r < OUT_DIM; r++) begin
      b_ref[r] = 0;
      for (int c = 0; c < LEN; c++) w_ref[r][c] = 0;
    end
  endtask

  // -----------------------
  // Test cases
  // -----------------------
  task automatic run_deterministic();
    init_zero_all();
    // Deterministic values: populate first ACTIVE_N cols and first ACTIVE_M rows; pad the rest with 0.
    for (int c = 0; c < ACTIVE_N; c++) begin
      x_ref[c] = i8_t'((c*3) - 20);
    end
    for (int r = 0; r < ACTIVE_M; r++) begin
      b_ref[r] = i32_t'(r - 5);
      for (int c = 0; c < ACTIVE_N; c++) begin
        w_ref[r][c] = i8_t'((r*7) - (c*2));
      end
    end

    bias_en    = 1'b1;
    len_64     = 1'b0; // LEN=32
    out_dim_64 = 1'b0; // OUT_DIM=32

    pulse_clear_done();
    load_x();
    load_w();
    load_b();
    compute_golden();

    pulse_start();
    // Expected compute cycles: OUT_DIM*(LEN+1) ~= 32*33=1056, plus a few overhead cycles.
    wait_done_with_timeout(5000);

    // done should stay asserted until clear_done
    if (done !== 1'b1) begin
      $display("TB_GEMV: FAIL deterministic: done not asserted");
      $fatal(1);
    end

    // Reset y index for clean readout
    pulse_clear_done();
    read_and_check_y("deterministic");

    $display("TB_GEMV: PASS deterministic");
  endtask

  task automatic run_randomized();
    int unsigned seed;
    int unsigned initial_seed;
    int unsigned r;
    init_zero_all();
    initial_seed = 32'hC0FFEE01;
    seed = initial_seed;

    for (int c = 0; c < ACTIVE_N; c++) begin
      r = $urandom(seed);
      x_ref[c] = i8_t'(r[7:0]);
    end

    for (int r_i = 0; r_i < ACTIVE_M; r_i++) begin
      b_ref[r_i] = i32_t'($signed($urandom(seed)));
      for (int c = 0; c < ACTIVE_N; c++) begin
        r = $urandom(seed);
        w_ref[r_i][c] = i8_t'(r[7:0]);
      end
    end

    bias_en    = 1'b1;
    len_64     = 1'b0;
    out_dim_64 = 1'b0;

    pulse_clear_done();
    load_x();
    load_w();
    load_b();
    compute_golden();

    pulse_start();
    wait_done_with_timeout(5000);

    pulse_clear_done();
    read_and_check_y("randomized");

    $display("TB_GEMV: PASS randomized (seed=0x%08x)", initial_seed);
  endtask

  task automatic run_boundary();
    init_zero_all();
    // Boundary/extremes: use max/min int8 to validate signed multiply and int32 accumulation.
    for (int c = 0; c < ACTIVE_N; c++) begin
      x_ref[c] = 8'sd127;
    end

    // Row 0: all +127 => positive sum
    for (int c = 0; c < ACTIVE_N; c++) w_ref[0][c] = 8'sd127;
    // Row 1: all -128 => negative sum
    for (int c = 0; c < ACTIVE_N; c++) w_ref[1][c] = -8'sd128;
    // Row 2: alternating +127/-128
    for (int c = 0; c < ACTIVE_N; c++) w_ref[2][c] = (c[0] ? -8'sd128 : 8'sd127);
    // Row 3: alternating -128/+127
    for (int c = 0; c < ACTIVE_N; c++) w_ref[3][c] = (c[0] ? 8'sd127 : -8'sd128);

    // No bias for boundary test
    bias_en    = 1'b0;
    len_64     = 1'b0;
    out_dim_64 = 1'b0;

    pulse_clear_done();
    load_x();
    load_w();
    // Still load biases (zeros) to keep sequencing consistent
    load_b();
    compute_golden();

    pulse_start();
    wait_done_with_timeout(5000);

    pulse_clear_done();
    read_and_check_y("boundary");

    $display("TB_GEMV: PASS boundary/extremes");
  endtask

  // -----------------------
  // Main
  // -----------------------
  initial begin
    $dumpfile("tb_gemv.vcd");
    $dumpvars(0, tb_gemv);

    reset_dut();

    // Sanity: in IDLE after reset, busy/done should be 0.
    if (busy !== 1'b0 || done !== 1'b0) begin
      $display("TB_GEMV: FAIL: expected busy=0 done=0 after reset (busy=%0b done=%0b)", busy, done);
      $fatal(1);
    end

    run_deterministic();
    run_randomized();
    run_boundary();

    $display("TB_GEMV: ALL TESTS PASS");
    $finish;
  end

endmodule

