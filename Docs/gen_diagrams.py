#!/usr/bin/env python3
"""Generate draw.io (.drawio.xml) files for Figures 2-9 of the TinyFormer report.
Labels use only XML-safe characters (no raw < & "); newlines via &#10;.
"""
import os

OUTDIR = "/home/ronweinstein/workspace/university/Final_Project/TinyFormer_algo/Docs"

def vert(cid, value, x, y, w, h, style):
    return (f'        <mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">\n'
            f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" />\n'
            f'        </mxCell>\n')

def edge(cid, src, tgt, value="", style=""):
    base = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;"
    if not style:
        style = base + "startArrow=classic;startFill=1;endArrow=classic;endFill=1;"
    return (f'        <mxCell id="{cid}" value="{value}" style="{style}" edge="1" parent="1" source="{src}" target="{tgt}">\n'
            f'          <mxGeometry relative="1" as="geometry" />\n'
            f'        </mxCell>\n')

def wrap(name, dia_id, cells, pw=900, ph=720):
    return (f'<mxfile host="app.diagrams.net" type="device">\n'
            f'  <diagram name="{name}" id="{dia_id}">\n'
            f'    <mxGraphModel dx="900" dy="650" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{pw}" pageHeight="{ph}" '
            f'math="0" shadow="0" background="#ffffff">\n'
            f'      <root>\n'
            f'        <mxCell id="0" />\n'
            f'        <mxCell id="1" parent="0" />\n'
            f'{cells}'
            f'      </root>\n'
            f'    </mxGraphModel>\n'
            f'  </diagram>\n'
            f'</mxfile>\n')

# styles
S_TITLE = "text;html=1;align=center;verticalAlign=middle;fontStyle=1;fontSize=16;"
S_BOX   = "rounded=1;whiteSpace=wrap;html=1;fontSize=12;fillColor=#dae8fc;strokeColor=#6c8ebf;"
S_ACC   = "rounded=1;whiteSpace=wrap;html=1;fontSize=12;fillColor=#d5e8d4;strokeColor=#82b366;"
S_BUS   = "rounded=0;whiteSpace=wrap;html=1;fontSize=12;fontStyle=1;fillColor=#ffe6cc;strokeColor=#d79b00;"
S_MEM   = "rounded=1;whiteSpace=wrap;html=1;fontSize=12;fillColor=#fff2cc;strokeColor=#d6b656;"
S_IO    = "rounded=1;whiteSpace=wrap;html=1;fontSize=12;fillColor=#f8cecc;strokeColor=#b85450;"
S_NOTE  = "rounded=0;whiteSpace=wrap;html=1;fontSize=11;dashed=1;align=left;verticalAlign=top;fillColor=#ffffff;strokeColor=#999999;"
S_CONT  = "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;fontSize=14;fillColor=#ffffff;strokeColor=#666666;arcSize=3;"

def title(txt, w=820):
    return vert("title", txt, 40, 10, w, 30, S_TITLE)

files = {}

# ---------------- Figure 2: LiteX SoC architecture ----------------
c = ""
c += title("Figure 2 — LiteX SoC Architecture")
c += vert("cont", "LiteX-generated SoC (Nexys4DDR, VexRiscv RV32IM @ 100 MHz)", 40, 50, 820, 500, S_CONT)
c += vert("cpu", "VexRiscv RV32IM core&#10;(DOT8 plugin)", 90, 120, 200, 90, S_BOX)
c += vert("bus", "Wishbone / CSR&#10;Interconnect", 360, 120, 70, 380, S_BUS)
c += vert("uart", "UART", 500, 120, 300, 55, S_IO)
c += vert("timer", "Timer0 (cycle counter)", 500, 185, 300, 55, S_MEM)
c += vert("explut", "EXP-LUT CSR peripheral", 500, 250, 300, 55, S_ACC)
c += vert("gemv", "GEMV CSR peripheral", 500, 315, 300, 55, S_ACC)
c += vert("dram", "LiteDRAM DDR2 controller", 500, 420, 300, 55, S_MEM)
c += vert("ddr2", "DDR2 SDRAM (on-board)", 540, 600, 220, 55, S_MEM)
c += edge("e1", "cpu", "bus")
c += edge("e2", "bus", "uart")
c += edge("e3", "bus", "timer")
c += edge("e4", "bus", "explut")
c += edge("e5", "bus", "gemv")
c += edge("e6", "bus", "dram")
c += edge("e7", "dram", "ddr2")
files["Figure2_LiteX_SoC_Architecture.drawio.xml"] = wrap("Figure 2 - LiteX SoC Architecture", "fig2", c, 900, 720)

# ---------------- Figure 3: DOT8 pipeline ----------------
c = ""
c += title("Figure 3 — DOT8 Custom Instruction in the VexRiscv Pipeline")
c += vert("fetch", "Fetch", 60, 90, 110, 60, S_BOX)
c += vert("decode", "Decode&#10;opcode 0x0B, funct7 0x01", 190, 90, 150, 60, S_BOX)
c += vert("exec", "Execute stage — Dot8 plugin", 360, 80, 300, 300, S_CONT)
c += vert("m0", "a0 × b0", 390, 150, 100, 35, S_ACC)
c += vert("m1", "a1 × b1", 390, 195, 100, 35, S_ACC)
c += vert("m2", "a2 × b2", 390, 240, 100, 35, S_ACC)
c += vert("m3", "a3 × b3", 390, 285, 100, 35, S_ACC)
c += vert("add", "Σ&#10;adder&#10;tree", 540, 195, 90, 95, S_ACC)
c += vert("wb", "Writeback&#10;int32 result to rd", 700, 90, 150, 60, S_BOX)
c += vert("inp", "rs1 = 4×int8 packed&#10;rs2 = 4×int8 packed&#10;(sign-extended)", 60, 230, 220, 90, S_NOTE)
c += edge("p1", "fetch", "decode")
c += edge("p2", "decode", "exec", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("p3", "exec", "wb", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
for i, m in enumerate(["m0","m1","m2","m3"]):
    c += edge(f"a{i}", m, "add", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("ai", "inp", "exec", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#999999;dashed=1;endArrow=open;startArrow=none;")
files["Figure3_DOT8_Pipeline.drawio.xml"] = wrap("Figure 3 - DOT8 Pipeline", "fig3", c, 900, 440)

# ---------------- Figure 4: EXP-LUT interface ----------------
c = ""
c += title("Figure 4 — EXP-LUT Peripheral Interface")
c += vert("cpu", "CPU / firmware&#10;(softmax)", 60, 180, 180, 110, S_BOX)
c += vert("idx", "index CSR&#10;write idx (0..15)", 330, 110, 200, 60, S_IO)
c += vert("rom", "16-entry Q10 exp() ROM&#10;lut[ index[3:0] ]  (combinational)&#10;1024, 754, 556, ..., 12", 330, 210, 280, 100, S_ACC)
c += vert("val", "value CSR&#10;read Q10 value [15:0]", 330, 350, 200, 60, S_IO)
c += edge("e1", "cpu", "idx", value="write index (0..15)", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e2", "idx", "rom", value="addr = index[3:0]", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e3", "rom", "val", value="Q10 value", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e4", "val", "cpu", value="read value (~12 cyc)", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
files["Figure4_EXP_LUT_Interface.drawio.xml"] = wrap("Figure 4 - EXP-LUT Interface", "fig4", c, 760, 470)

# ---------------- Figure 5: GEMV dataflow ----------------
c = ""
c += title("Figure 5 — GEMV Peripheral Data-Flow", 820)
c += vert("cpu", "CPU / firmware&#10;pack4_i8():&#10;4 int8 to 1 word", 50, 90, 180, 130, S_BOX)
c += vert("xmem", "X memory (32-bit words)", 320, 80, 210, 50, S_MEM)
c += vert("wmem", "W memory (32-bit words)", 320, 145, 210, 50, S_MEM)
c += vert("bmem", "B memory (int32 bias)", 320, 210, 210, 50, S_MEM)
c += vert("mac", "4-lane signed MAC&#10;dot4 = Σ x·w  (1 word/cycle)", 590, 95, 240, 80, S_ACC)
c += vert("acc", "int32 accumulator&#10;(+ bias preload)", 590, 200, 240, 60, S_ACC)
c += vert("ymem", "Y memory (int32 results)", 590, 290, 240, 50, S_MEM)
c += vert("fsm", "FSM:&#10;S_IDLE → S_COMPUTE → S_DONE&#10;256 cycles per 32×32 matvec", 320, 300, 210, 90, S_NOTE)
c += edge("e1", "cpu", "xmem", value="X_IN (packed)", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e2", "cpu", "wmem", value="W_IN (packed)", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e3", "cpu", "bmem", value="B_IN", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e4", "xmem", "mac", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e5", "wmem", "mac", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e6", "mac", "acc", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e7", "bmem", "acc", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#999999;dashed=1;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e8", "acc", "ymem", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
c += edge("e9", "ymem", "cpu", value="Y_OUT / Y_NEXT", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
files["Figure5_GEMV_Dataflow.drawio.xml"] = wrap("Figure 5 - GEMV Data-Flow", "fig5", c, 900, 430)

# ---------------- Figure 6: TinyFormer encoder pipeline ----------------
c = ""
c += title("Figure 6 — TinyFormer Encoder Pipeline")
steps = [
    ("input", "Input X  [16×32]", S_MEM, 70, 50),
    ("qkv", "Q/K/V Linear Projections&#10;W_q, W_k, W_v  (int8, ≫7)  [GEMV]", S_BOX, 150, 70),
    ("attn", "Scaled Dot-Product Attention (streaming)&#10;scores ≫5 → softmax [EXP-LUT] → Σ wᵢⱼ·V", S_BOX, 260, 90),
    ("oproj", "Output Projection W_o  [GEMV]&#10;+ residual  (X + ·)", S_BOX, 390, 70),
    ("ffn1", "FFN layer 1: W_ff1 [32→64] + ReLU  [GEMV]", S_BOX, 490, 60),
    ("ffn2", "FFN layer 2: W_ff2 [64→32]  [GEMV]&#10;+ residual", S_BOX, 580, 70),
    ("output", "Output  [16×32]", S_MEM, 680, 50),
]
for cid, val, st, y, h in steps:
    c += vert(cid, val, 300, y, 300, h, st)
order = [s[0] for s in steps]
for i in range(len(order)-1):
    c += edge(f"f{i}", order[i], order[i+1], style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=classic;endFill=1;startArrow=none;")
# side annotations
c += vert("n_dot8", "DOT8&#10;accelerates the&#10;attention dot products", 60, 250, 190, 90, S_NOTE)
c += vert("n_lut", "EXP-LUT&#10;replaces the runtime&#10;softmax exp()", 640, 250, 190, 90, S_NOTE)
c += edge("an1", "n_dot8", "attn", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#999999;dashed=1;endArrow=open;startArrow=none;")
c += edge("an2", "n_lut", "attn", style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#999999;dashed=1;endArrow=open;startArrow=none;")
files["Figure6_TinyFormer_Encoder_Pipeline.drawio.xml"] = wrap("Figure 6 - Encoder Pipeline", "fig6", c, 900, 800)

# ---------------- Figure 7: Baseline cycle breakdown (horizontal bars) ----------------
c = ""
c += title("Figure 7 — Baseline Cycle Breakdown (75.9 M cycles / 759 ms per inference)")
rows = [
    ("Softmax exp()", 71, "#f8cecc", "#b85450"),
    ("Matrix-vector mult.", 21, "#d5e8d4", "#82b366"),
    ("UART output", 5, "#dae8fc", "#6c8ebf"),
    ("Attention dot products", 1, "#ffe6cc", "#d79b00"),
    ("Misc (residual/pool/cls)", 2, "#fff2cc", "#d6b656"),
]
scale = 5.0  # px per percent
x0 = 250
y = 80
for i, (lab, pct, fill, stroke) in enumerate(rows):
    w = max(int(pct * scale), 6)
    c += vert(f"lbl{i}", lab, 40, y, 200, 30, "text;html=1;align=right;verticalAlign=middle;fontSize=12;")
    bstyle = f"rounded=0;whiteSpace=wrap;html=1;fontSize=11;fillColor={fill};strokeColor={stroke};"
    c += vert(f"bar{i}", f"{pct}%", x0, y, w, 30, bstyle)
    y += 45
# axis baseline
c += vert("axis", "", x0, 70, 1, y-70, "endArrow=none;html=1;strokeColor=#000000;")
files["Figure7_Baseline_Cycle_Breakdown.drawio.xml"] = wrap("Figure 7 - Baseline Breakdown", "fig7", c, 820, 380)

# ---------------- Figure 8: latency comparison (vertical bars) ----------------
c = ""
c += title("Figure 8 — End-to-End Latency per Inference (lower is better)")
modes = [
    ("Baseline&#10;759.00 ms&#10;1.00×", 759.0, "#f8cecc", "#b85450"),
    ("accel_all v1&#10;190.67 ms&#10;3.98×", 190.67, "#dae8fc", "#6c8ebf"),
    ("accel_all v2&#10;157.55 ms&#10;4.82×", 157.55, "#d5e8d4", "#82b366"),
]
base_y = 480
maxh = 380
mx = max(m[1] for m in modes)
x = 170
for i, (lab, val, fill, stroke) in enumerate(modes):
    h = int(val / mx * maxh)
    yb = base_y - h
    bstyle = f"rounded=0;whiteSpace=wrap;html=1;fontSize=11;fillColor={fill};strokeColor={stroke};"
    c += vert(f"bar{i}", "", x, yb, 110, h, bstyle)
    c += vert(f"val{i}", f"{val:.2f} ms", x, yb-30, 110, 24, "text;html=1;align=center;fontSize=11;fontStyle=1;")
    c += vert(f"lbl{i}", lab, x, base_y+10, 110, 70, "text;html=1;align=center;verticalAlign=top;fontSize=11;")
    x += 200
# axes
c += vert("yaxis", "", 130, 90, 1, base_y-90, "endArrow=none;html=1;strokeColor=#000000;")
c += vert("xaxis", "", 130, base_y, 600, 1, "endArrow=none;html=1;strokeColor=#000000;")
files["Figure8_Latency_Comparison.drawio.xml"] = wrap("Figure 8 - Latency Comparison", "fig8", c, 820, 620)

# ---------------- Figure 9: GEMV v1 vs v2 cycles (vertical bars) ----------------
c = ""
c += title("Figure 9 — GEMV v1 → v2 Cycle Reduction (per inference)")
bars = [
    ("accel_all v1&#10;19.07 M cyc&#10;3.98×", 19.07, "#dae8fc", "#6c8ebf"),
    ("accel_all v2&#10;15.76 M cyc&#10;4.82×", 15.76, "#d5e8d4", "#82b366"),
]
base_y = 440
maxh = 320
mx = max(b[1] for b in bars)
x = 200
for i, (lab, val, fill, stroke) in enumerate(bars):
    h = int(val / mx * maxh)
    yb = base_y - h
    bstyle = f"rounded=0;whiteSpace=wrap;html=1;fontSize=11;fillColor={fill};strokeColor={stroke};"
    c += vert(f"bar{i}", "", x, yb, 130, h, bstyle)
    c += vert(f"val{i}", f"{val:.2f} M", x, yb-30, 130, 24, "text;html=1;align=center;fontSize=11;fontStyle=1;")
    c += vert(f"lbl{i}", lab, x, base_y+10, 130, 70, "text;html=1;align=center;verticalAlign=top;fontSize=11;")
    x += 230
c += vert("note", "≈ 3.3 M cycles saved by the&#10;4-lane packed-CSR GEMV upgrade", 470, 150, 230, 70, S_NOTE)
c += vert("yaxis", "", 160, 100, 1, base_y-100, "endArrow=none;html=1;strokeColor=#000000;")
c += vert("xaxis", "", 160, base_y, 480, 1, "endArrow=none;html=1;strokeColor=#000000;")
files["Figure9_GEMV_v1_v2_Cycles.drawio.xml"] = wrap("Figure 9 - GEMV v1 vs v2", "fig9", c, 760, 580)

# ---- write all ----
for fn, content in files.items():
    with open(os.path.join(OUTDIR, fn), "w", encoding="utf-8") as fh:
        fh.write(content)
    print("wrote", fn)
