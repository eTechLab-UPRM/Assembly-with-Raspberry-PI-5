# 2D Convolution on the Raspberry Pi: Python → C → Assembly

The same 2D convolution written in Python, in C and in ARM64 assembly, and
timed on a photo taken with the Raspberry Pi camera. The goal is to see how much speed
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
libraries, the kernel is not flipped.

Every part of the lab processes a **2592 × 1944 grayscale photo** taken with
the Raspberry Pi camera (`photo.pgm`), with an **edge-detection kernel**:

```
-1 -1 -1
-1  8 -1
-1 -1 -1
```

Flat areas give 0 and edges give large values, so the output shows the
outlines of the photo. Python takes about 9 seconds on a Raspberry Pi 5. What
the photo shows does not change the amount of work, so all students' times
are comparable.

## The versions

| Version | File | What changes |
| --- | --- | --- |
| Python | `conv_bench.py` | Four nested loops. Every `+` and `*` is interpreted while the program runs. |
| C v1 column order | `src/conv.c` | The same four loops, compiled to machine code by `gcc -O2`, with the outer loop over columns: every step jumps a whole row in memory. |
| C v2 row order | `src/conv.c` | The same code with the two outer loops swapped, so it walks memory in the order the image is stored. |
| ASM v1 brute force | `src/conv_asm.S` | A direct translation of the C loops: every index is recomputed with `MUL`. |
| ASM v2 pointers | `src/conv_asm.S` | No index arithmetic in the loop: pointers walk the image, the kernel stays in registers. |
| ASM v3 MAC | `src/conv_student.S` | v2 with each `MUL` + `ADD` pair fused into one `MADD`. **Written by the students.** |
| ASM v4 NEON | `src/conv_asm.S` | Vector instructions compute 4 output pixels at once. |

`src/conv_student.S` starts as a copy of v2 with 8 places marked `TODO`.
Until a student completes it, the v3 row is correct but as fast as v2.

## Setup and running the lab

A Raspberry Pi camera is required. It must be connected **before** the Pi is
powered on.

**[docs/SETUP.md](docs/SETUP.md)** takes a student from a new Raspberry Pi
to the open notebook, step by step, with troubleshooting. In short:

```sh
uname -m                                         # must print aarch64
rpicam-hello --list-cameras                      # must list the camera
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
python3 conv_demo.py photo            # take the photo: photo.pgm
python3 conv_bench.py                 # all versions on the photo
python3 conv_bench.py --skip-python   # quick: compare against C v1 instead
python3 conv_demo.py                  # interactive console demo
```

`conv_bench.py` prints one row per version: the median time of 5 runs (Python
runs once), how many times faster it is than Python, and `OK` if its output
equals the Python output. A `MISMATCH` row does not count, however fast it
is. `NOT BUILT` means the library is missing or did not assemble: run `make`
and read its error.

If the camera is not detected, `take_photo()` / `conv_demo.py photo` stops
with the steps to check the connection. Without `photo.pgm`, the benchmark
and the race ask for the photo first.

`conv_demo.py` has three modes:

| Mode | What students see |
| --- | --- |
| 1. Step by step | A small grid of numbers with the 3 × 3 kernel highlighted as it slides. Each output pixel shows its 9 multiplications, and the output fills in. `Enter` advances one pixel, `a` runs on its own. |
| 2. Photo | Takes the photo with the camera (`rpicam-still`, 3 seconds of preview) and saves it as `photo.pgm`: the brightness plane of a YUV420 capture, which is the grayscale image. |
| 3. Race | Python processes the photo on a CPU core of its own while, on another core, the six C and assembly versions process it one after another, so no version slows another one down. Panel 1 shows each version's progress and time; panel 2 shows how many photos each C and assembly version could process in the time Python has used so far (Python's time ÷ that version's time). |

In the notebook, `notebook_image()` shows the photo next to its edges,
computed with C on the whole photo, plus a zoom on the pixel values and the
kernel. Photos are not committed (`.gitignore`).

## Fair timings

- Close other programs and let the board cool between runs.
- Use a heatsink or fan, and check for throttling after a run with
  `vcgencmd get_throttled` (`0x0` means no throttling).
- Report the board model with the results: times differ between models.

## Files

```
lab.ipynb           the lab: explanations, code cells and questions
docs/SETUP.md       setup guide for students, from a new Raspberry Pi and its camera
conv_bench.py       Python version, runner and timing table
conv_demo.py        camera, console demo, and the notebook's step-by-step, image and race
src/conv.c          C versions: column order and row order
src/conv_asm.S      ARM64 assembly v1, v2 and v4, commented line by line
src/conv_student.S  ARM64 assembly v3, the students' exercise
Makefile            builds build/libconv_c.so, libconv_asm.so, libconv_student.so
```
