# What this folder is (in simple words)

This is a COPY of an external academic codebase: the "PULP-Transformer" kernels from the
paper *Optimizing the Deployment of Tiny Transformers on Low-Power MCUs* (Jung, Burrello,
Scherer, Conti, Benini - arXiv:2404.02945). It targets GAP9 and ARM microcontrollers,
NOT our FPGA.

It is kept here because it is the INTELLECTUAL STARTING POINT of the project: ideas like
streaming attention (never build the full S x S attention matrix in memory) come from this
work. Our actual implementation is a clean rewrite in `litex_port/common/tinyformer.c`.

Nothing in this folder is compiled into our firmware or bitstream.
