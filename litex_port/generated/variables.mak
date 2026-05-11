PACKAGES=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata bios
PACKAGE_DIRS=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libc /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libcompiler_rt /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libbase /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libfatfs /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitespi /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitedram /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libliteeth /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitesdcard /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitesata /home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/bios
LIBS=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata
TRIPLE=riscv64-unknown-elf
CPU=vexriscv
CPUFAMILY=riscv
CPUFLAGS=-march=rv32i2p0_m     -mabi=ilp32 -D__vexriscv__
CPUENDIANNESS=little
CLANG=0
CPU_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/cores/cpu/vexriscv
SOC_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc
PICOLIBC_DIRECTORY=/home/yonatang/litex-project/third_party/litex/pythondata-software-picolibc/pythondata_software_picolibc/data
PICOLIBC_FORMAT=integer
COMPILER_RT_DIRECTORY=/home/yonatang/litex-project/third_party/litex/pythondata-software-compiler_rt/pythondata_software_compiler_rt/data
export BUILDINC_DIRECTORY
BUILDINC_DIRECTORY=/home/yonatang/litex-project/hw/build/software/include
LIBC_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libc
LIBCOMPILER_RT_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libcompiler_rt
LIBBASE_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libbase
LIBFATFS_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libfatfs
LIBLITESPI_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitespi
LIBLITEDRAM_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitedram
LIBLITEETH_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/libliteeth
LIBLITESDCARD_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitesdcard
LIBLITESATA_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/liblitesata
BIOS_DIRECTORY=/home/yonatang/.local/lib/python3.10/site-packages/litex/soc/software/bios
LTO=0
BIOS_CONSOLE_FULL=1