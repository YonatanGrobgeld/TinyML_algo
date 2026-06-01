#!/usr/bin/env python3
"""Render publication-quality figures (1-9) for the TinyFormer report as PNGs."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = "/home/ronweinstein/workspace/university/Final_Project/TinyFormer_algo/Docs/figures"
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})

COL = {
    "cpu":  ("#dae8fc", "#4a6fa5"),
    "acc":  ("#d5e8d4", "#5e8c4f"),
    "bus":  ("#ffe6cc", "#c47f1a"),
    "mem":  ("#fff2cc", "#bfa130"),
    "io":   ("#f8cecc", "#a8403d"),
    "out":  ("#e1d5e7", "#7d5599"),
    "note": ("#ffffff", "#9a9a9a"),
    "cont": ("#ffffff", "#5a5a5a"),
}
EDGE = "#333333"


def canvas(w_in, h_in, W, H):
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.set_aspect("equal"); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, kind="cpu", fs=11, bold=False, align="center", dashed=False):
    fc, ec = COL[kind]
    rs = max(1.8, min(5.0, 0.32 * min(w, h)))
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rs}",
                       linewidth=1.5, edgecolor=ec, facecolor=fc, zorder=3,
                       linestyle="--" if dashed else "-")
    ax.add_patch(p)
    if align == "center":
        tx, ha = x + w / 2, "center"
    else:
        tx, ha = x + 8, "left"
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs,
            weight="bold" if bold else "normal", zorder=4, color="#111111")
    return (x, y, w, h)


def container(ax, x, y, w, h, title, fs=13):
    fc, ec = COL["cont"]
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8",
                       linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=1)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h - 7, title, ha="center", va="center",
            fontsize=fs, weight="bold", color="#333333", zorder=2)


def C(b): return (b[0] + b[2] / 2, b[1] + b[3] / 2)
def R(b): return (b[0] + b[2], b[1] + b[3] / 2)
def L(b): return (b[0], b[1] + b[3] / 2)
def T(b): return (b[0] + b[2] / 2, b[1] + b[3])
def B(b): return (b[0] + b[2] / 2, b[1])


def arrow(ax, p1, p2, bidir=False, color=EDGE, lw=1.6, dashed=False, conn="arc3,rad=0", label=None, lfs=9):
    style = "<|-|>" if bidir else "-|>"
    fa = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=13, color=color,
                         lw=lw, zorder=2, shrinkA=3, shrinkB=3,
                         connectionstyle=conn, linestyle="--" if dashed else "-")
    ax.add_patch(fa)
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 4, label, ha="center", va="bottom", fontsize=lfs,
                color="#444444", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


def elbow(ax, pts, color=EDGE, lw=1.6, label=None, lpos=None):
    for i in range(len(pts) - 2):
        ax.add_patch(FancyArrowPatch(pts[i], pts[i + 1], arrowstyle="-", mutation_scale=1,
                                     color=color, lw=lw, zorder=2, shrinkA=0, shrinkB=0))
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=13,
                                 color=color, lw=lw, zorder=2, shrinkA=0, shrinkB=3))
    if label and lpos:
        ax.text(lpos[0], lpos[1], label, ha="center", va="bottom", fontsize=9, color="#444444",
                zorder=5, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


def title(ax, W, H, txt):
    ax.text(W / 2, H - 4, txt, ha="center", va="top", fontsize=15, weight="bold", color="#111111")


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white", pad_inches=0.2)
    plt.close(fig)
    print("wrote", name)


# ============ Figure 1 — System block diagram ============
def fig1():
    W, H = 120, 84
    fig, ax = canvas(12, 8.4, W, H)
    title(ax, W, H, "Figure 1 — TinyFormer System Block Diagram")
    container(ax, 6, 10, 108, 64, "Nexys4DDR FPGA  ·  Xilinx Artix-7 xc7a100t  ·  100 MHz")
    cpu = box(ax, 12, 44, 30, 16, "VexRiscv\nRV32IM CPU\n+ DOT8 plugin", "cpu", 10, bold=True)
    fw  = box(ax, 12, 20, 30, 18, "Firmware modes\n(compile-time):\nbaseline\naccel_all\n(DOT8 + EXP-LUT + GEMV)", "note", 8.5, dashed=True)
    bus = box(ax, 54, 20, 12, 40, "LiteX\nSoC Bus\n(Wishbone\n/ CSR)", "bus", 8.5, bold=True)
    lut = box(ax, 80, 50, 32, 11, "EXP-LUT (MMIO)\n16-entry Q10 ROM", "acc", 9.5)
    gem = box(ax, 80, 37, 32, 11, "GEMV (MMIO)\n4-lane int8 MAC", "acc", 9.5)
    ddr = box(ax, 80, 24, 32, 10, "DDR2 SDRAM\nfirmware + weights", "mem", 9.5)
    ua  = box(ax, 80, 13, 32, 8,  "UART (115200 baud)", "io", 9.5)
    ser = box(ax, 80, 1, 32, 8,   "Serial out:\nENC_CKSUM + class", "out", 9)
    arrow(ax, R(cpu), L(bus), bidir=True)
    for p in (lut, gem, ddr, ua):
        arrow(ax, R(bus), L(p), bidir=True)
    arrow(ax, B(ua), T(ser))
    save(fig, "Figure1_System_Block_Diagram.png")


# ============ Figure 2 — LiteX SoC architecture ============
def fig2():
    W, H = 120, 78
    fig, ax = canvas(12, 7.8, W, H)
    title(ax, W, H, "Figure 2 — LiteX SoC Architecture")
    container(ax, 6, 8, 108, 62, "LiteX-generated SoC  ·  VexRiscv RV32IM @ 100 MHz")
    cpu = box(ax, 12, 40, 30, 16, "VexRiscv\nRV32IM core\n(DOT8 plugin)", "cpu", 9.5, bold=True)
    bus = box(ax, 54, 16, 12, 40, "Wishbone\n/ CSR\nInter-\nconnect", "bus", 8.5, bold=True)
    ua  = box(ax, 80, 53, 32, 9, "UART", "io", 10)
    tm  = box(ax, 80, 42, 32, 9, "Timer0 (cycle counter)", "mem", 9)
    lut = box(ax, 80, 31, 32, 9, "EXP-LUT CSR peripheral", "acc", 9)
    gem = box(ax, 80, 20, 32, 9, "GEMV CSR peripheral", "acc", 9)
    dctl= box(ax, 80, 9, 32, 9, "LiteDRAM DDR2 controller", "mem", 8.5)
    ddr = box(ax, 82, 1, 28, 6, "DDR2 SDRAM (on-board)", "mem", 8.5)
    arrow(ax, R(cpu), L(bus), bidir=True)
    for p in (ua, tm, lut, gem, dctl):
        arrow(ax, R(bus), L(p), bidir=True)
    arrow(ax, B(dctl), T(ddr), bidir=True)
    save(fig, "Figure2_LiteX_SoC_Architecture.png")


# ============ Figure 3 — DOT8 pipeline ============
def fig3():
    W, H = 130, 60
    fig, ax = canvas(13, 6, W, H)
    title(ax, W, H, "Figure 3 — DOT8 Custom Instruction in the VexRiscv Pipeline")
    fet = box(ax, 6, 40, 18, 10, "Fetch", "cpu", 11)
    dec = box(ax, 30, 40, 22, 10, "Decode\nop 0x0B / f7 0x01", "cpu", 9.5)
    container(ax, 58, 8, 40, 44, "Execute — Dot8 plugin")
    m = []
    for i, yy in enumerate((34, 27, 20, 13)):
        m.append(box(ax, 61, yy, 16, 6, f"a{i}×b{i}", "acc", 9.5))
    add = box(ax, 82, 20, 12, 14, "Σ\nadder\ntree", "acc", 9.5, bold=True)
    wb  = box(ax, 104, 40, 22, 10, "Writeback\nint32 → rd", "cpu", 9.5)
    inp = box(ax, 6, 18, 30, 14, "rs1 = 4×int8 packed\nrs2 = 4×int8 packed\n(sign-extended)", "note", 9, dashed=True)
    arrow(ax, R(fet), L(dec))
    arrow(ax, R(dec), (58, 37))
    for b in m:
        arrow(ax, R(b), L(add))
    arrow(ax, R(add), L(wb))
    arrow(ax, T(inp), (61, 32), dashed=True, color="#888888", conn="arc3,rad=-0.2")
    save(fig, "Figure3_DOT8_Pipeline.png")


# ============ Figure 4 — EXP-LUT interface ============
def fig4():
    W, H = 92, 56
    fig, ax = canvas(9.2, 5.6, W, H)
    title(ax, W, H, "Figure 4 — EXP-LUT Peripheral Interface")
    cpu = box(ax, 6, 20, 22, 16, "CPU / firmware\n(softmax)", "cpu", 10.5, bold=True)
    idx = box(ax, 40, 38, 28, 9, "index CSR\nwrite idx (0..15)", "io", 9.5)
    rom = box(ax, 40, 22, 40, 12, "16-entry Q10 exp() ROM\nlut[index[3:0]]  (combinational)\n1024, 754, 556, …, 12", "acc", 9, bold=True)
    val = box(ax, 40, 6, 28, 9, "value CSR\nread Q10 value", "io", 9.5)
    arrow(ax, R(cpu), L(idx), conn="arc3,rad=-0.25", label="write index")
    arrow(ax, B(idx), T(rom))
    arrow(ax, B(rom), T(val))
    arrow(ax, L(val), R(cpu), conn="arc3,rad=-0.25")
    ax.text(72, 18.5, "Q10 value", fontsize=9, color="#444444", ha="center", va="center")
    ax.text(30, 13, "read (~12 cyc)", fontsize=9, color="#444444", ha="center", va="center")
    save(fig, "Figure4_EXP_LUT_Interface.png")


# ============ Figure 5 — GEMV dataflow ============
def fig5():
    W, H = 128, 56
    fig, ax = canvas(12.8, 5.6, W, H)
    title(ax, W, H, "Figure 5 — GEMV Peripheral Data-Flow")
    cpu = box(ax, 4, 26, 24, 18, "CPU / firmware\npack4_i8():\n4 int8 → 1 word", "cpu", 9.5, bold=True)
    xm = box(ax, 40, 42, 26, 8, "X memory (32-bit words)", "mem", 9)
    wm = box(ax, 40, 32, 26, 8, "W memory (32-bit words)", "mem", 9)
    bm = box(ax, 40, 22, 26, 8, "B memory (int32 bias)", "mem", 9)
    fsm = box(ax, 4, 6, 24, 12, "FSM:\nIDLE → COMPUTE → DONE\n256 cyc / 32×32", "note", 8.5, dashed=True)
    mac = box(ax, 80, 36, 30, 12, "4-lane signed MAC\ndot4 = Σ x·w  (1 word/cyc)", "acc", 9, bold=True)
    acc = box(ax, 80, 24, 30, 9, "int32 accumulator\n(+ bias)", "acc", 9)
    ym  = box(ax, 80, 12, 30, 9, "Y memory (int32 results)", "mem", 9)
    arrow(ax, R(cpu), L(xm), label="X_IN")
    arrow(ax, R(cpu), L(wm), label="W_IN")
    arrow(ax, R(cpu), L(bm), label="B_IN")
    arrow(ax, R(xm), L(mac))
    arrow(ax, R(wm), L(mac))
    arrow(ax, B(mac), T(acc))
    arrow(ax, R(bm), L(acc), dashed=True, color="#888888")
    arrow(ax, B(acc), T(ym))
    elbow(ax, [B(ym), (95, 4), (2, 4), (2, 35), L(cpu)],
          label="Y_OUT / Y_NEXT", lpos=(52, 4.5))
    save(fig, "Figure5_GEMV_Dataflow.png")


# ============ Figure 6 — encoder pipeline ============
def fig6():
    W, H = 96, 110
    fig, ax = canvas(9.6, 11, W, H)
    title(ax, W, H, "Figure 6 — TinyFormer Encoder Pipeline")
    steps = [
        ("Input X  [16×32]", "mem", 90, 8, 10),
        ("Q/K/V Linear Projections\nW_q, W_k, W_v  (int8, ≫7)   [GEMV]", "cpu", 76, 11, 10),
        ("Scaled Dot-Product Attention (streaming)\nscores ≫5 → softmax [EXP-LUT] → Σ wᵢⱼ·V", "cpu", 60, 13, 9.5),
        ("Output Projection W_o   [GEMV]\n+ residual  (X + ·)", "cpu", 46, 11, 9.5),
        ("FFN layer 1: W_ff1 [32→64] + ReLU   [GEMV]", "cpu", 34, 9, 9.5),
        ("FFN layer 2: W_ff2 [64→32]   [GEMV]\n+ residual", "cpu", 20, 11, 9.5),
        ("Output  [16×32]", "mem", 8, 8, 10),
    ]
    boxes = []
    for txt, kind, y, h, fs in steps:
        boxes.append(box(ax, 30, y, 40, h, txt, kind, fs, bold=(kind == "mem")))
    for i in range(len(boxes) - 1):
        arrow(ax, B(boxes[i]), T(boxes[i + 1]))
    # residual side arrows
    arrow(ax, L(boxes[0]), L(boxes[3]), color="#a8403d", conn="arc3,rad=-0.45", label="residual")
    arrow(ax, L(boxes[2]), L(boxes[5]), color="#a8403d", conn="arc3,rad=-0.4", label="residual")
    nd = box(ax, 73, 58, 21, 12, "DOT8\naccelerates the\nattention dot products", "note", 8, dashed=True)
    nl = box(ax, 73, 44, 21, 12, "EXP-LUT\nreplaces runtime\nsoftmax exp()", "note", 8, dashed=True)
    arrow(ax, L(nd), R(boxes[2]), dashed=True, color="#888888")
    arrow(ax, L(nl), R(boxes[2]), dashed=True, color="#888888", conn="arc3,rad=0.2")
    save(fig, "Figure6_TinyFormer_Encoder_Pipeline.png")


# ============ Figure 7 — baseline breakdown (barh) ============
def fig7():
    cats = ["Softmax exp()", "Matrix-vector mult.", "UART output",
            "Misc (resid/pool/cls)", "Attention dot prod."]
    pct = [71, 21, 5, 2, 1]
    cyc = ["53.8 M", "16.3 M", "4.0 M", "0.8 M", "1.0 M"]
    colors = ["#e8918d", "#8fc77f", "#7fa8d8", "#e8cf6a", "#d79b00"]
    fig, ax = plt.subplots(figsize=(9.5, 4.6)); fig.patch.set_facecolor("white")
    y = range(len(cats))[::-1]
    bars = ax.barh(list(y), pct, color=colors, edgecolor="#444444", height=0.62)
    for yi, p, c in zip(y, pct, cyc):
        ax.text(p + 1.2, yi, f"{p}%  ({c} cyc)", va="center", ha="left", fontsize=10.5, weight="bold")
    ax.set_yticks(list(y)); ax.set_yticklabels(cats, fontsize=11)
    ax.set_xlim(0, 88); ax.set_xlabel("Share of baseline cycles (%)", fontsize=11)
    ax.set_title("Figure 7 — Baseline Cycle Breakdown\n75.9 M cycles · 759 ms per inference",
                 fontsize=14, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, ls=":", alpha=0.5); ax.set_axisbelow(True)
    save(fig, "Figure7_Baseline_Cycle_Breakdown.png")


# ============ Figure 8 — latency bars ============
def fig8():
    labels = ["Baseline", "accel_all"]
    ms = [759.00, 157.55]
    spd = ["1.00×", "4.82×"]
    colors = ["#e8918d", "#8fc77f"]
    fig, ax = plt.subplots(figsize=(7.8, 5.2)); fig.patch.set_facecolor("white")
    bars = ax.bar(labels, ms, color=colors, edgecolor="#444444", width=0.6)
    for b, m, s in zip(bars, ms, spd):
        ax.text(b.get_x() + b.get_width() / 2, m + 12, f"{m:.2f} ms", ha="center", fontsize=11, weight="bold")
        ax.text(b.get_x() + b.get_width() / 2, m / 2, s, ha="center", fontsize=13, weight="bold", color="#222222")
    ax.set_ylabel("Latency per inference (ms)", fontsize=11)
    ax.set_ylim(0, 840)
    ax.set_title("Figure 8 — End-to-End Latency (lower is better)", fontsize=14, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, ls=":", alpha=0.5); ax.set_axisbelow(True)
    save(fig, "Figure8_Latency_Comparison.png")


# ============ Figure 9 — GEMV v1 vs v2 ============
def fig9():
    labels = ["accel_all v1\n(byte-wide GEMV)", "accel_all v2\n(4-lane packed GEMV)"]
    mc = [19.07, 15.76]
    spd = ["3.98×", "4.82×"]
    colors = ["#7fa8d8", "#8fc77f"]
    fig, ax = plt.subplots(figsize=(7.0, 5.2)); fig.patch.set_facecolor("white")
    bars = ax.bar(labels, mc, color=colors, edgecolor="#444444", width=0.55)
    for b, m, s in zip(bars, mc, spd):
        ax.text(b.get_x() + b.get_width() / 2, m + 0.3, f"{m:.2f} M cyc", ha="center", fontsize=11, weight="bold")
        ax.text(b.get_x() + b.get_width() / 2, m / 2, s, ha="center", fontsize=13, weight="bold", color="#222222")
    ax.plot([0, 1.34], [19.07, 19.07], ls=(0, (4, 3)), color="#999999", lw=1.2, zorder=1)
    ax.annotate("", xy=(1.34, 15.76), xytext=(1.34, 19.07),
                arrowprops=dict(arrowstyle="<->", color="#a8403d", lw=1.8))
    ax.text(1.40, 17.4, "−3.3 M cyc\n(−17%)", ha="left", va="center", fontsize=9.5,
            color="#a8403d", weight="bold")
    ax.set_xlim(-0.55, 1.95)
    ax.set_ylabel("Cycles per inference (millions)", fontsize=11)
    ax.set_ylim(0, 22)
    ax.set_title("Figure 9 — GEMV v1 → v2 Cycle Reduction", fontsize=14, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, ls=":", alpha=0.5); ax.set_axisbelow(True)
    save(fig, "Figure9_GEMV_v1_v2_Cycles.png")


for f in (fig1, fig2, fig3, fig4, fig5, fig7, fig8):
    f()
print("done")
