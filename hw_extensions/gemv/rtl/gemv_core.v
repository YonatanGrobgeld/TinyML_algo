/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  The MATRIX ENGINE (v3) in Verilog: computes Y = W*X + b for int8 matrix/vector with
 *  32 or 64 dimensions. The CPU first streams X, W, b into internal memories (4 packed
 *  int8 values per 32-bit write - 4x fewer bus writes than v1), then pulses 'start'.
 *  A state machine (IDLE -> COMPUTE -> DONE) sweeps each row: the 'dot4' 4-lane MAC does
 *  4 multiplies+adds per column word, now PIPELINED across fetch -> multiply -> accumulate
 *  stages (result bit-identical to v2) so the design meets timing at 100 MHz. It raises
 *  'done'; the CPU reads results one at a time via Y_OUT, poking Y_NEXT to advance.
 *  BIG PICTURE: The hardware that removed the 21% matvec bottleneck; 32x32 matvec in ~288 compute cycles.
 * ==========================================================================
 */

/*
 * GEMV core v3: Y = W * X + b (optional).
 * int8 W, X; int32 b, Y.  LEN and OUT_DIM = 32 or 64.
 *
 * v3 vs v2: identical interface and numerical result, but the inner
 * "fetch -> 4-lane multiply -> accumulate" datapath is now PIPELINED so it
 * closes timing at 100 MHz. v2 did all of that in one clock (row -> w_addr ->
 * async w_mem read -> 4 signed mults -> adder tree -> 32-bit accumulate),
 * which was the -6.3 ns critical path (row_reg -> acc_reg).
 *
 * Pipeline (per column word):
 *   Stage 1 (fetch)      : register x_mem[col] and w_mem[w_addr] -> *_word_r
 *                          (registered read => w_mem infers block RAM)
 *   Stage 2 (multiply)   : 4-lane signed int8 dot product -> dot4_r
 *   Stage 3 (accumulate) : acc += dot4_r
 * Columns of a row are issued in order and drained before the next row, so
 * the accumulation order (and thus every int32 result) is identical to v2.
 */

module gemv_core #(
    parameter MAX_LEN     = 64,
    parameter MAX_OUT     = 64,
    parameter W_ADDR_BITS = 10        /* MAX_OUT*MAX_LEN/4 = 1024 words */
) (
    input  wire         clk,
    input  wire         reset,

    /* Write ports (driven by wrapper when CPU writes X_IN, W_IN, B_IN).
     * X_IN / W_IN now carry 4 packed int8 lanes per write (32 bits total). */
    input  wire         x_wr_en,
    input  wire [31:0]  x_wr_data,
    input  wire         w_wr_en,
    input  wire [31:0]  w_wr_data,
    input  wire         b_wr_en,
    input  wire [31:0]  b_wr_data,

    input  wire         start,
    input  wire         len_64,
    input  wire         out_dim_64,
    input  wire         bias_en,

    output reg          busy,
    output reg          done,

    input  wire         clear_done,

    input  wire         y_rd_en,
    output wire [31:0]  y_rd_data
);

    localparam LEN_WBITS  = 4;        /* word index for X: 0..15  (MAX_LEN/4) */
    localparam OUT_BITS   = 6;        /* row index: 0..63 */

    /* Packed 32-bit memories — one word holds 4 int8 lanes */
    reg [31:0]         x_mem [0:(MAX_LEN/4)-1];               /* 16 words   */
    reg [31:0]         w_mem [0:((MAX_OUT*MAX_LEN)/4)-1];     /* 1024 words */
    reg signed [31:0]  b_mem [0:MAX_OUT-1];                   /* 64 entries */
    reg signed [31:0]  y_mem [0:MAX_OUT-1];

    /* Write word-indices (reset on clear_done) */
    reg [LEN_WBITS-1:0]    x_wr_idx;
    reg [W_ADDR_BITS-1:0]  w_wr_idx;
    reg [OUT_BITS-1:0]     b_wr_idx;
    reg [OUT_BITS-1:0]     y_rd_idx;

    /* Effective dims in WORDS */
    wire [LEN_WBITS:0] LEN_WORDS;     /* 8 (LEN=32) or 16 (LEN=64) */
    wire [OUT_BITS:0]  OUT_DIM;
    assign LEN_WORDS = len_64     ? 16 : 8;
    assign OUT_DIM   = out_dim_64 ? 64 : 32;

    /* FSM */
    localparam [2:0] S_IDLE    = 3'd0,
                     S_COMPUTE = 3'd1,
                     S_DONE    = 3'd2;
    reg [2:0] state;

    /* row in OUT space; col = issue pointer in WORD space inside one row */
    reg [OUT_BITS-1:0]    row;
    reg [LEN_WBITS:0]     col;
    reg signed [31:0]     acc;
    reg [LEN_WBITS:0]     acc_cnt;   /* accumulations completed this row */

    /* Pipeline registers */
    reg [31:0]            x_word_r, w_word_r;   /* stage 1: fetched operands  */
    reg                   v_fetch;              /* stage 1 produced a valid op */
    reg signed [31:0]     dot4_r;               /* stage 2: 4-lane dot product */
    reg                   v_mul;                /* stage 2 valid               */

    /* W row base in words: row * LEN_WORDS */
    wire [W_ADDR_BITS-1:0] w_row_base;
    wire [W_ADDR_BITS-1:0] w_addr;
    assign w_row_base = len_64 ? ({4'd0, row} * 10'd16) : ({4'd0, row} * 10'd8);
    assign w_addr     = w_row_base + {6'd0, col[LEN_WBITS-1:0]};

    /* Stage-1 combinational reads (registered below into *_word_r) */
    wire        issue    = (col < LEN_WORDS);
    wire [31:0] x_word_c = x_mem[col[LEN_WBITS-1:0]];
    wire [31:0] w_word_c = w_mem[w_addr];

    /* Stage-2 combinational: 4-lane signed dot product of REGISTERED operands */
    wire signed [31:0] dot4_c =
          ($signed(x_word_r[ 7: 0]) * $signed(w_word_r[ 7: 0]))
        + ($signed(x_word_r[15: 8]) * $signed(w_word_r[15: 8]))
        + ($signed(x_word_r[23:16]) * $signed(w_word_r[23:16]))
        + ($signed(x_word_r[31:24]) * $signed(w_word_r[31:24]));

    assign y_rd_data = y_mem[y_rd_idx];

    /* --- Write path: X, W (packed 32-bit), B (32-bit) --- */
    always @(posedge clk) begin
        if (reset || clear_done) begin
            x_wr_idx <= 0;
            w_wr_idx <= 0;
            b_wr_idx <= 0;
        end else begin
            if (x_wr_en) begin
                x_mem[x_wr_idx] <= x_wr_data;
                x_wr_idx <= x_wr_idx + 1;
            end
            if (w_wr_en) begin
                w_mem[w_wr_idx] <= w_wr_data;
                w_wr_idx <= w_wr_idx + 1;
            end
            if (b_wr_en) begin
                b_mem[b_wr_idx[OUT_BITS-1:0]] <= b_wr_data;
                b_wr_idx <= b_wr_idx + 1;
            end
        end
    end

    /* --- Y read pointer: advance on read, reset on clear_done --- */
    always @(posedge clk) begin
        if (reset || clear_done)
            y_rd_idx <= 0;
        else if (y_rd_en)
            y_rd_idx <= y_rd_idx + 1;
    end

    /* --- Compute FSM (pipelined) --- */
    always @(posedge clk) begin
        if (reset) begin
            state   <= S_IDLE;
            busy    <= 0;
            done    <= 0;
            row     <= 0;
            col     <= 0;
            acc     <= 0;
            acc_cnt <= 0;
            v_fetch <= 0;
            v_mul   <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    if (start && !busy) begin
                        state   <= S_COMPUTE;
                        busy    <= 1;
                        done    <= 0;
                        row     <= 0;
                        col     <= 0;
                        acc     <= bias_en ? b_mem[0] : 32'sd0;
                        acc_cnt <= 0;
                        v_fetch <= 0;
                        v_mul   <= 0;
                    end
                end

                S_COMPUTE: begin
                    /* Stage 1: issue read for `col`, register the operands */
                    if (issue) begin
                        x_word_r <= x_word_c;
                        w_word_r <= w_word_c;
                        v_fetch  <= 1'b1;
                        col      <= col + 1'b1;
                    end else begin
                        v_fetch  <= 1'b0;
                    end

                    /* Stage 2: multiply registered operands */
                    dot4_r <= dot4_c;
                    v_mul  <= v_fetch;

                    /* Stage 3: accumulate */
                    if (v_mul) begin
                        acc     <= acc + dot4_r;
                        acc_cnt <= acc_cnt + 1'b1;
                    end

                    /* Row complete: all LEN_WORDS terms accumulated into acc.
                     * (v_mul is 0 in this cycle, so no accumulate conflicts.) */
                    if (acc_cnt == LEN_WORDS) begin
                        y_mem[row] <= acc;
                        if (row + 1 >= OUT_DIM) begin
                            state <= S_DONE;
                            busy  <= 1'b0;
                        end else begin
                            row     <= row + 1'b1;
                            col     <= 0;
                            acc     <= bias_en ? b_mem[row + 1] : 32'sd0;
                            acc_cnt <= 0;
                            v_fetch <= 1'b0;
                            v_mul   <= 1'b0;
                        end
                    end
                end

                S_DONE: begin
                    done <= 1;
                    if (clear_done) begin
                        state <= S_IDLE;
                        done  <= 0;
                    end else
                        state <= S_DONE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule