# 2D Convolution on the Raspberry Pi: Python → C → Assembly

The same 2D convolution written in Python, in C and in ARM64 assembly, and
timed on the same data on a Raspberry Pi. The goal is to see how much speed
each step down in language depth buys, and how the way assembly is written
changes its speed.

The lab is the Jupyter notebook **`lab.ipynb`**: it reads like a short book
chapter, runs the code in its cells, and has the questions students answer.

## The operation

A 3 × 3 kernel slides over an `H × W` image of 32-bit integers. Each output
pixel is the sum of the 9 pixels under the kernel, each multiplied by its
coefficient:

```
out[y][x] = Σ (ky = 0..2) Σ (kx = 0..2)  in[y + ky][x + kx] · k[ky][kx]
```

The output is `(H − 2) × (W − 2)` (no padding). As in deep-learning
libraries, the kernel is not flipped. The benchmark uses a 2400 × 2400 image
of random numbers, which takes Python about 10 seconds on a Raspberry Pi 5.

## The versions

| Version | File | What changes |
| --- | --- | --- |
| Python | `conv_bench.py` | Four nested loops. Every `+` and `*` is interpreted while the program runs. |
| C | `src/conv.c` | The same four loops, compiled to machine code by `gcc -O2`. |
| ASM v1 brute force | `src/conv_asm.S` | A direct translation of the C loops: every index is recomputed with `MUL`. |
| ASM v2 pointers | `src/conv_asm.S` | No index arithmetic in the loop: pointers walk the image, the kernel stays in registers. |
| ASM v3 MAC | `src/conv_student.S` | v2 with each `MUL` + `ADD` pair fused into one `MADD`. **Written by the students.** |
| ASM v4 NEON | `src/conv_asm.S` | Vector instructions compute 4 output pixels at once. |

`src/conv_student.S` starts as a copy of v2 with 8 places marked `TODO`.
Until a student completes it, the v3 row is correct but as fast as v2.

## Setup and running the lab

**[docs/SETUP.md](docs/SETUP.md)** takes a student from a new Raspberry Pi
to the open notebook, step by step, with troubleshooting. In short:

```sh
uname -m                                         # must print aarch64
sudo apt update
sudo apt install -y git build-essential python3-venv
git clone https://github.com/kevinnt16/Assembly-with-Raspberry-PI-5.git
cd Assembly-with-Raspberry-PI-5
make && python3 conv_bench.py --test             # must end in "all OK"
python3 -m venv ~/jupyter-env
~/jupyter-env/bin/pip install --index-url https://pypi.org/simple --resume-retries 5 --timeout 60 notebook
~/jupyter-env/bin/jupyter notebook lab.ipynb
```

## Without Jupyter

Everything also runs from the terminal, with the Python standard library only:

```sh
make                                  # build the C and assembly libraries
python3 conv_bench.py --test          # correctness check, must end with "all OK"
python3 conv_bench.py                 # all versions, 2400 x 2400 image
python3 conv_bench.py --skip-python   # quick: compare against C instead
python3 conv_demo.py                  # interactive console demo
```

`conv_bench.py` prints one row per version: the median time of 5 runs (Python
runs once), how many times faster it is than Python, and `OK` if its output
equals the Python output. A `MISMATCH` row does not count, however fast it
is. `NOT BUILT` means the library is missing or did not assemble: run `make`
and read its error.

`conv_demo.py` has two modes:

| Mode | What students see |
| --- | --- |
| 1. Step by step | A small grid of numbers with the 3 × 3 kernel highlighted as it slides. Each output pixel shows its 9 multiplications, and the output fills in. `Enter` advances one pixel, `a` runs on its own. |
| 2. Race | Python, C and assembly v4 start the same image at the same time, each on its own CPU core. Each bar is the progress of that one image: C and assembly fill theirs almost at once and show their finish time, while Python's crawls. Meanwhile, C and assembly keep processing copies and count how many they finish before Python ends. |

The race shares memory and the CPU between the three versions, so it is a
visual comparison; use `conv_bench.py` for exact timings.

## Fair timings

- Close other programs and let the board cool between runs.
- Use a heatsink or fan, and check for throttling after a run with
  `vcgencmd get_throttled` (`0x0` means no throttling).
- Report the board model with the results: times differ between models.

## Files

```
lab.ipynb           the lab: explanations, code cells and questions
docs/SETUP.md       setup guide for students, from a new Raspberry Pi
conv_bench.py       Python version, runner and timing table
conv_demo.py        console demo, and the notebook's step-by-step and race
src/conv.c          C version
src/conv_asm.S      ARM64 assembly v1, v2 and v4, commented line by line
src/conv_student.S  ARM64 assembly v3, the students' exercise
Makefile            builds build/libconv_c.so, libconv_asm.so, libconv_student.so
```
