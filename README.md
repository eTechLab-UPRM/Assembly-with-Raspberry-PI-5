# 2D Convolution on the Raspberry Pi: Python → C → Assembly

The same 2D convolution written in Python, in C and in ARM64 assembly, and
timed on a photo taken with the Raspberry Pi camera. The goal is to see how much speed
each step down in language depth buys, and how the way assembly is written
changes its speed.

It is a mini project for students, built around the
Jupyter notebook **`project.ipynb`**: it reads like a short book chapter, runs the
code in its cells, has students write three of the versions, and has the
questions they answer.

## The operation

A 3 × 3 kernel slides over an `H × W` image of 32-bit integers. Each output
pixel is the sum of the 9 pixels under the kernel, each multiplied by its
coefficient:

```
out[y][x] = Σ (ky = 0..2) Σ (kx = 0..2)  in[y + ky][x + kx] · k[ky][kx]
```

The output is `(H − 2) × (W − 2)` (no padding). As in deep-learning
libraries, the kernel is not flipped.

Every part of the project processes a **2592 × 1944 grayscale photo** taken with
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
| C v1 column order | `src/conv.c` | The same four loops, compiled to machine code by `gcc -O2`, with the outer loop over columns: every step jumps a whole row in memory. Its loops and operations are commented with their RISC-V (Ripes) translation. |
| C v2 row order | `src/conv_student_c.c` | The same convolution walking the image row by row, the order it is stored in memory. **Written by the students.** |
| ASM v1 brute force | `src/conv_student_v1.S` | A direct translation of C v2: every index is recomputed with `MUL`. **Students write its core.** |
| ASM v2 pointers | `src/conv_asm.S` | No index arithmetic in the loop: pointers walk the image, the kernel stays in registers. |
| ASM v3 MAC | `src/conv_student.S` | v2 with each `MUL` + `ADD` pair fused into one `MADD`. **Written by the students.** |
| ASM v4 NEON | `src/conv_asm.S` | Vector instructions compute 4 output pixels at once. |

Students write three versions in notebook cells, never editing the files by
hand:

- **C v2** (Part 3): they get the function's signature and write the four
  loops, with hints. `build_c_v2()` puts it into `src/conv_student_c.c`.
- **ASM v1** (Part 5): the function is given (size check, `oh`/`ow`, the
  four loops with named labels as in Ripes, the pixel load); they write its
  core: the coefficient load, the multiply-add and the store of the output
  pixel, about 9 instructions. `build_v1()` puts it into
  `src/conv_student_v1.S`.
- **ASM v3** (Part 7): `src/conv_student.S` starts as v2 with its first `MUL` +
  `ADD` pair already fused into `MADD`, as a worked example, and 7 pairs
  marked `TODO`; they edit the code of one output pixel. `build_v3()` puts
  it into the file.

Both functions (in `conv_demo.py`) write the code between the file's
`YOUR CODE` markers, build it, point any compiler error to the line of the
cell, and run the benchmark in a separate process, so code that crashes or
never ends is reported instead of stopping the notebook. Until a student's
version is correct, the race leaves it out.

## Setup and running the project

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
~/jupyter-env/bin/jupyter notebook project.ipynb
```

## Without Jupyter

Everything also runs from the terminal, with the Python standard library only:

```sh
make                                  # build the C and assembly libraries
python3 conv_bench.py --test          # correctness check, must end with "all OK"
python3 conv_demo.py photo            # take the photo: photo.pgm
python3 conv_bench.py                 # all versions on the photo
python3 conv_bench.py --skip-python   # quick: compare against C v1 instead
python3 conv_bench.py --only "C v1"   # one version only (Python, C v1, ... ASM v4)
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
project.ipynb       the project: explanations, code cells and questions
docs/SETUP.md       setup guide for students, from a new Raspberry Pi and its camera
conv_bench.py       Python version, runner and timing table
conv_demo.py        camera, console demo, and the notebook's step-by-step, image and race
src/conv.c          C v1 (column order), with RISC-V comments
src/conv_student_c.c  C v2 (row order), the students' C exercise
src/conv_asm.S      ARM64 assembly v2 and v4, commented line by line
src/conv_student_v1.S  ARM64 assembly v1, the students' first assembly exercise
src/conv_student.S  ARM64 assembly v3, the students' second assembly exercise
Makefile            builds the five libraries in build/
```
