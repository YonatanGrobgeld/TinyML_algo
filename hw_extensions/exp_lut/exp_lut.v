/*
 * Exp LUT — softmax helper for TinyFormer.
 *
 * Maps a signed index (e.g. -15..0) to a fixed-point exp(value) approximation.
 * Input: index (e.g. 5-bit signed). Output: 16-bit fixed-point value (Q10 or Q15).
 *
 * Standalone module; no LiteX CSR glue yet. For use as MMIO peripheral:
 * - Register: write index → latch; read data → LUT output.
 */

module exp_lut (
    input  wire        clk,
    input  wire        reset,

    /* Index into LUT. Signed: 0 = exp(0), -1 = exp(-1), ... -15 = exp(-15). */
    input  wire [4:0]  index,

    /* Output: exp value in fixed-point (e.g. Q10). Combinatorial or registered. */
    output wire [15:0] value
);

    /* LUT: 16 entries for index 0 (exp(0)) down to 15 (exp(-15)). Q10.
     * Values match litex_port/tinyformer.c exp_lut[16] exactly for drop-in replacement.
     */
    reg [15:0] lut [0:15];

    initial begin
        lut[0]  = 1024;  /* ~1.0 * 2^10 */
        lut[1]  = 754;
        lut[2]  = 556;
        lut[3]  = 410;
        lut[4]  = 302;
        lut[5]  = 223;
        lut[6]  = 165;
        lut[7]  = 122;
        lut[8]  = 90;
        lut[9]  = 67;
        lut[10] = 50;
        lut[11] = 37;
        lut[12] = 28;
        lut[13] = 21;
        lut[14] = 16;
        lut[15] = 12;
    end

    /* Index 0..15: map signed 5-bit to 0..15 (0 = exp(0), 1 = exp(-1), ... 15 = exp(-15)). */
    wire [3:0] addr = index[3:0];

    assign value = lut[addr];

endmodule
