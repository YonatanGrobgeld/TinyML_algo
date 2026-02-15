# DOT8 — RISC-V encoding plan

## Opcode

- **opcode:** custom-0 = `0x0B` (RISC-V standard custom opcode for custom-0 space).
- **funct7:** `0x01` for DOT8 (4-lane signed int8 dot-product). Use this value in the VexRiscv plugin decode and in C inline asm.

## Instruction format (R-type)

| 31–25    | 24–20 | 19–15 | 14–12 | 11–7   | 6–0   |
|----------|-------|-------|-------|--------|-------|
| funct7   | rs2   | rs1   | funct3 | rd     | opcode |
| 7 bit    | 5 bit | 5 bit | 3 bit | 5 bit  | 0x0B   |

- **rs1:** first operand (packed int8 lanes).
- **rs2:** second operand (packed int8 lanes).
- **rd:** destination register; int32 result of the dot-product (or MAC, if accumulative variant is defined).

## Packing (fixed for C and RTL)

- **4×int8 per register:** Lane 0 in LSB (byte 0), lane 1 in byte 1, lane 2 in byte 2, lane 3 in byte 3 (little-endian). **Signed** int8; each lane must be sign-extended to int32 before multiply.  
  `rd = sext(rs1[0])*sext(rs2[0]) + ... + sext(rs1[3])*sext(rs2[3])`.
- **C API:** Use `dot8_pack(a)` from `hw_extensions/dot8/sw/dot8.h` so packing matches hardware.
- **Extended use:** Multiple DOT8 instructions can be used in sequence to cover D=32 (e.g. 8 instructions for 4×8 lanes), with software accumulating the partial sums.

funct3 can be used later to select variants (e.g. 4-lane vs 8-lane, or dot vs MAC) if needed.

## Summary

- **Opcode:** 0x0B (custom-0).
- **funct7:** reserved for DOT8.
- **rs1, rs2:** packed int8 lanes.
- **rd:** int32 dot-product result.
