/*
 * ==========================================================================
 *  WHAT THIS FILE DOES (in simple words):
 *  Adds ONE NEW INSTRUCTION to the CPU itself. VexRiscv (the RISC-V CPU) is written in
 *  SpinalHDL/Scala and accepts 'plugins'; this plugin watches every instruction, and when
 *  it sees opcode 0x0B with funct7 0x01 (a code reserved for custom use), it treats the two
 *  source registers as 4 packed int8 numbers each, does 4 multiplies + adds them (one adder
 *  tree, 4 DSP blocks) in a single cycle, and writes the int32 result to the destination
 *  register like any normal instruction.
 *  BIG PICTURE: The hardware half of DOT8; the C half is hw_extensions/dot8/sw/dot8.c.
 * ==========================================================================
 */

/*
 * VexRiscv plugin: DOT8/DOT4 custom instruction (4-lane signed int8 dot-product).
 *
 * Opcode: custom-0 = 0x0B. funct7 = 0x01.
 * rs1, rs2 = packed int8 (lane 0 = LSB .. lane 3 = MSB); rd = int32 result.
 * rd = sum_{i=0..3} signext8(rs1.byte[i]) * signext8(rs2.byte[i])
 *
 * Single-cycle execute; no multi-cycle stalls. Matches hw_extensions/dot8/sw/dot8.c and encoding.md.
 */

package vexriscv.plugin

import spinal.core._
import spinal.lib._
import vexriscv.{DecoderService, Stageable, VexRiscv}

object Dot8Plugin {
  val DOT8_FUNCT7 = B(0x01, 7 bits)
  val DOT8_OPCODE = B(0x0B, 7 bits)

  object DOT8_OPCODE_STAGEABLE extends Stageable(Bool())
  object DOT8_RD extends Stageable(SInt(32 bits))
}

class Dot8Plugin extends Plugin[VexRiscv] {

  override def setup(pipeline: VexRiscv): Unit = {
    import pipeline.config._
    import Dot8Plugin._
    val decoder = pipeline.service(classOf[DecoderService])
    decoder.addDefault(DOT8_OPCODE_STAGEABLE, False)
  }

  override def build(pipeline: VexRiscv): Unit = {
    import pipeline._
    import pipeline.config._
    import Dot8Plugin._

    val decode = pipeline.decode
    val execute = pipeline.execute
    val writeback = pipeline.writeback

    val instr = decode.input(INSTRUCTION)
    /* SIMPLE WORDS: watch every instruction; when the low 7 bits are 0x0B and
     * the top 7 bits are 0x01, this instruction is OURS. */
    val isDot8 = (instr(6 downto 0) === DOT8_OPCODE) && (instr(31 downto 25) === DOT8_FUNCT7)

    decode.insert(DOT8_OPCODE_STAGEABLE) := isDot8
    when(isDot8) {
      decode.insert(REGFILE_WRITE_VALID) := True
    }

    val rs1Bits = execute.input(RS1).asBits
    val rs2Bits = execute.input(RS2).asBits

    val a0 = rs1Bits(7 downto 0).asSInt.resize(32)
    val a1 = rs1Bits(15 downto 8).asSInt.resize(32)
    val a2 = rs1Bits(23 downto 16).asSInt.resize(32)
    val a3 = rs1Bits(31 downto 24).asSInt.resize(32)
    val b0 = rs2Bits(7 downto 0).asSInt.resize(32)
    val b1 = rs2Bits(15 downto 8).asSInt.resize(32)
    val b2 = rs2Bits(23 downto 16).asSInt.resize(32)
    val b3 = rs2Bits(31 downto 24).asSInt.resize(32)

    /* SIMPLE WORDS: the whole point - 4 signed multiplies and a 3-add tree,
     * done in the single execute stage (maps to 4 DSP blocks on the FPGA). */
    val dotResult = (a0 * b0) + (a1 * b1) + (a2 * b2) + (a3 * b3)
    execute.insert(DOT8_RD) := dotResult

    /* SIMPLE WORDS: in the writeback stage, put our answer into the
     * destination register - exactly like any normal instruction would. */
    when(writeback.input(DOT8_OPCODE_STAGEABLE)) {
      writeback.output(REGFILE_WRITE_DATA) := writeback.input(DOT8_RD).asBits
    }
    /* If your VexRiscv build muxes REGFILE_WRITE_DATA from multiple plugins, add DOT8_RD as an input to that mux when DOT8_OPCODE_STAGEABLE (see e.g. MulPlugin). */
  }
}
