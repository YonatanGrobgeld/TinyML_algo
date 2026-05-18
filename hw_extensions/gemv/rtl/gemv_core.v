/*
 * GEMV core v2: Y = W * X + b (optional).
 * int8 W, X; int32 b, Y.  LEN and OUT_DIM = 32 or 64.
 *
 * V2 OPTIMIZATIONS vs V1:
 *  1) Packed 32-bit data writes (4 bytes per CSR write) — cuts CPU↔GEMV
 *     MMIO traffic by 4x for X and W loading.
 *  2) 4-lane parallel signed int8 MAC per cycle — cuts compute time by 4x.
 *
 * Memory layout:
 *  - x_mem, w_mem are now 32-bit-wide word memories (one packed word per addr).
 *  - Byte 0 of each word = LSB (lane 0), byte 3 = MSB (lane 3).
 *  - Index is in WORDS, not bytes.
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

    /* row in OUT space; col in WORD space inside one row */
    reg [OUT_BITS-1:0]    row;
    reg [LEN_WBITS:0]     col;
    reg signed [31:0]     acc;

    /* W row base in words: row * LEN_WORDS */
    wire [W_ADDR_BITS-1:0] w_row_base;
    wire [W_ADDR_BITS-1:0] w_addr;
    assign w_row_base = len_64 ? ({4'd0, row} * 10'd16) : ({4'd0, row} * 10'd8);
    assign w_addr     = w_row_base + {6'd0, col[LEN_WBITS-1:0]};

    /* 4-lane parallel signed dot product on the fetched X word and W word */
    wire [31:0] x_word = x_mem[col[LEN_WBITS-1:0]];
    wire [31:0] w_word = w_mem[w_addr];
    wire signed [31:0] dot4 =
          ($signed(x_word[ 7: 0]) * $signed(w_word[ 7: 0]))
        + ($signed(x_word[15: 8]) * $signed(w_word[15: 8]))
        + ($signed(x_word[23:16]) * $signed(w_word[23:16]))
        + ($signed(x_word[31:24]) * $signed(w_word[31:24]));

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

    /* --- FSM --- */
    always @(posedge clk) begin
        if (reset) begin
            state <= S_IDLE;
            busy  <= 0;
            done  <= 0;
            row   <= 0;
            col   <= 0;
            acc   <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    if (start && !busy) begin
                        state <= S_COMPUTE;
                        busy  <= 1;
                        done  <= 0;
                        row   <= 0;
                        col   <= 0;
                        acc   <= bias_en ? b_mem[0] : 32'sd0;
                    end
                end

                S_COMPUTE: begin
                    if (col < LEN_WORDS) begin
                        /* 4-lane MAC per cycle */
                        acc <= acc + dot4;
                        col <= col + 1;
                    end else begin
                        y_mem[row] <= acc;
                        row <= row + 1;
                        col <= 0;
                        if (row + 1 >= OUT_DIM) begin
                            state <= S_DONE;
                            busy  <= 0;
                        end else
                            acc <= bias_en ? b_mem[row + 1] : 32'sd0;
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
