/*
 * GEMV core: Y = W * X + b (optional).
 * int8 W, X; int32 b, Y. LEN and OUT_DIM configurable 32 or 64.
 * CSR-fed: external logic (LiteX wrapper) pushes X, W, b via write ports;
 * core computes on start; external logic reads Y via read port.
 */

module gemv_core #(
    parameter MAX_LEN     = 64,
    parameter MAX_OUT    = 64,
    parameter W_ADDR_BITS = 12    /* MAX_OUT * MAX_LEN = 4096 */
) (
    input  wire         clk,
    input  wire         reset,

    /* Write ports (driven by wrapper when CPU writes X_IN, W_IN, B_IN) */
    input  wire         x_wr_en,
    input  wire [7:0]   x_wr_data,
    input  wire         w_wr_en,
    input  wire [7:0]   w_wr_data,
    input  wire         b_wr_en,
    input  wire [31:0]  b_wr_data,

    /* Config and start (from CTRL) */
    input  wire         start,
    input  wire         len_64,      /* 0: LEN=32, 1: LEN=64 */
    input  wire         out_dim_64,   /* 0: OUT_DIM=32, 1: OUT_DIM=64 */
    input  wire         bias_en,

    /* Status */
    output reg          busy,
    output reg          done,

    /* Clear done / reset Y read pointer (from CTRL clear_done) */
    input  wire         clear_done,

    /* Read port for Y (wrapper asserts when CPU reads Y_OUT) */
    input  wire         y_rd_en,
    output wire [31:0]  y_rd_data
);

    localparam LEN_BITS   = 6;
    localparam OUT_BITS   = 6;

    /* Internal memories */
    reg signed [7:0]    x_mem [0:MAX_LEN-1];
    reg signed [7:0]    w_mem [0:(MAX_OUT*MAX_LEN)-1];
    reg signed [31:0]   b_mem [0:MAX_OUT-1];
    reg signed [31:0]   y_mem [0:MAX_OUT-1];

    /* Write indices (reset on clear_done) */
    reg [LEN_BITS-1:0]  x_wr_idx;
    reg [W_ADDR_BITS-1:0] w_wr_idx;
    reg [OUT_BITS-1:0] b_wr_idx;
    /* Read index for Y */
    reg [OUT_BITS-1:0]  y_rd_idx;

    /* Effective dimensions */
    wire [LEN_BITS:0]   LEN;      /* 32 or 64 */
    wire [OUT_BITS:0]  OUT_DIM;
    assign LEN     = len_64     ? 64 : 32;
    assign OUT_DIM = out_dim_64 ? 64 : 32;

    /* FSM */
    localparam [2:0] S_IDLE   = 3'd0,
                     S_COMPUTE = 3'd1,
                     S_DONE   = 3'd2;
    reg [2:0] state;

    /* Compute indices (current row, current column in row); col must reach LEN (64) so use LEN_BITS+1 */
    reg [OUT_BITS-1:0] row;
    reg [LEN_BITS:0]   col;  /* 0..LEN inclusive so col < LEN works for LEN=64 */
    reg signed [31:0]  acc;
    /* Explicitly sized row_base to avoid implicit-width bugs: row_base = row * LEN (32 or 64) */
    wire [W_ADDR_BITS-1:0] row_base;
    wire [W_ADDR_BITS-1:0] w_addr;
    assign row_base = len_64 ? ({6'd0, row} * 12'd64) : ({6'd0, row} * 12'd32);
    assign w_addr   = row_base + {5'd0, col};

    /* Y read output: combinatorial */
    assign y_rd_data = y_mem[y_rd_idx];

    /* --- Write path: X, W, B --- */
    always @(posedge clk) begin
        if (reset) begin
            x_wr_idx <= 0;
            w_wr_idx <= 0;
            b_wr_idx <= 0;
        end else if (clear_done) begin
            x_wr_idx <= 0;
            w_wr_idx <= 0;
            b_wr_idx <= 0;
        end else begin
            if (x_wr_en) begin
                x_mem[x_wr_idx[LEN_BITS-1:0]] <= x_wr_data;
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

    /* --- Y read index: advance on read, reset on clear_done --- */
    always @(posedge clk) begin
        if (reset || clear_done)
            y_rd_idx <= 0;
        else if (y_rd_en)
            y_rd_idx <= y_rd_idx + 1;
    end

    /* --- FSM: IDLE -> COMPUTE -> DONE --- */
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
                        done  <= 0;   /* clear stale DONE at start of new run */
                        row   <= 0;
                        col   <= 0;
                        acc   <= bias_en ? b_mem[0] : 32'sd0;
                    end
                end

                S_COMPUTE: begin
                    if (col < LEN) begin
                        /* Signed int8 * int8 -> int32; explicit $signed for clarity */
                        acc <= acc + ($signed(x_mem[col[LEN_BITS-1:0]]) * $signed(w_mem[w_addr]));
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
