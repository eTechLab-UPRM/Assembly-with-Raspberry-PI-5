# 2D Convolution on the Raspberry Pi: Python → C → Assembly

The same 2D convolution written three times, in Python, in C and in ARM64
assembly, and timed on the same data on a Raspberry Pi. The goal is to see
how much speed each step down in language depth buys.

## The operation

A 3 × 3 kernel slides over an `H × W` image of 32-bit integers. Each output
pixel is the sum of the 9 pixels under the kernel, each multiplied by its
coefficient:

```
out[y][x] = Σ (ky = 0..2) Σ (kx = 0..2)  in[y + ky][x + kx] · k[ky][kx]
```

The output is `(H − 2) × (W − 2)` (no padding). As in deep-learning
libraries, the kernel is not flipped.

## The three versions

| Version | File | What it shows |
| --- | --- | --- |
| Python | `conv_bench.py` | Four nested loops. Every `+` and `*` is interpreted while the program runs. |
| C | `src/conv.c` | The same four loops, compiled to machine code by `gcc -O2`. |
| Assembly | `src/conv_asm.S` | Written by hand: NEON vector instructions compute 4 output pixels at once, the kernel stays in registers, and pointers replace index arithmetic. |

## Requirements

- A Raspberry Pi with a 64-bit ARM CPU (Pi 5, 4, 3 or Zero 2 W) running
  Raspberry Pi OS **64-bit**. `uname -m` must print `aarch64`.
- `git`, `gcc` and `make`. Python 3 is already part of Raspberry Pi OS, and
  the script only uses its standard library.

## Setup on a new Raspberry Pi

```sh
uname -m                                   # must print aarch64
sudo apt update
sudo apt install -y git build-essential
git clone https://github.com/kevinnt16/Assembly-with-Raspberry-PI-5.git
cd Assembly-with-Raspberry-PI-5
```

## Build and run

```sh
make                              # builds build/libconv_c.so and build/libconv_asm.so
python3 conv_bench.py --test      # correctness check, must end with "all OK"
python3 conv_bench.py             # main run, 2048 x 2048 image
```

The main run prints one row per version: its time, how many times faster it
is than Python, and `OK` if its output equals the Python output. A
`MISMATCH` row does not count, however fast it is.

Pure Python takes several seconds on the 2048 × 2048 image. For a quicker
run, use a smaller image:

```sh
python3 conv_bench.py --size 512 512
```

## Interactive demo

`conv_demo.py` shows the convolution in the console, with a menu:

```sh
python3 conv_demo.py
```

| Mode | What students see |
| --- | --- |
| 1. Step by step | A small grid of numbers with the 3 × 3 kernel highlighted as it slides. Each output pixel shows its 9 multiplications, and the output fills in. `Enter` advances one pixel, `a` runs on its own. |
| 2. Picture | Shapes drawn in ASCII, before and after a kernel: edges, blur, sharpen, vertical edges, or 9 numbers they type themselves. The assembly version computes it, and the result is checked against C and Python. |
| 3. Race | Python, C and assembly start at the same time, each on its own CPU core. Python's bar crawls through one image while C and assembly count how many whole images they finish in that time. |

Each mode can also be opened directly: `python3 conv_demo.py step`,
`picture` or `race`. The race shares memory and the CPU between the three
versions, so it is a visual comparison; use `conv_bench.py` for exact timings.

## Fair timings

- Close other programs and let the board cool between runs.
- Use a heatsink or fan, and check for throttling after a run with
  `vcgencmd get_throttled` (`0x0` means no throttling).
- Report the board model with the results: times differ between models.

## Files

```
conv_bench.py     Python version, runner and timing table
conv_demo.py      interactive console demo (step by step, picture, race)
src/conv.c        C version
src/conv_asm.S    ARM64 assembly version, commented line by line
Makefile          builds build/libconv_c.so and build/libconv_asm.so
```

## Results on a Raspberry Pi 5

Raspberry Pi 5 Model B Rev 1.1, Python 3.13.5, 2048 × 2048 image
(37.7 M multiply-adds):

| Version | Time (ms) | vs Python | Check |
| --- | ---: | ---: | --- |
| Python | 7132.76 | 1.0x | OK |
| C (gcc -O2) | 136.78 | 52.1x | OK |
| Assembly (NEON) | 84.76 | 84.2x | OK |

C and assembly: median of 5 runs. The hand-written assembly is about 1.6×
faster than the compiler's C.
