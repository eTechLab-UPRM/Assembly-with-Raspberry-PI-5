#!/usr/bin/env python3
"""
conv_bench.py - the same 2D convolution in Python, C and ARM64 assembly.

All three versions get the same image and kernel. The C and assembly outputs
are checked against the Python output, and the time of each one is printed
in a single table.

    python3 conv_bench.py                 # 2048 x 2048 image
    python3 conv_bench.py --size 512 512  # smaller image, faster
    python3 conv_bench.py --test          # correctness test on many sizes

Build the libraries first with "make". Runs on a 64-bit Raspberry Pi
(uname -m must print aarch64). Only the Python standard library is used.
"""
import argparse
import ctypes
import os
import platform
import random
import statistics
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
KSIZE = 3


# ---------------------------------------------------------------------------
# Python version: lists of lists and four nested loops.
# ---------------------------------------------------------------------------
def conv_python(img, k):
    h, w = len(img), len(img[0])
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)
    out = [[0] * ow for _ in range(oh)]
    for y in range(oh):                  # every output row ...
        for x in range(ow):              # ... every output column
            acc = 0
            for ky in range(KSIZE):      # every kernel row
                for kx in range(KSIZE):  # every kernel column
                    acc += img[y + ky][x + kx] * k[ky][kx]
            out[y][x] = acc
    return out


# ---------------------------------------------------------------------------
# C and assembly versions, loaded from build/*.so with ctypes. Both have the
# C signature
#   void f(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
# and take the image as one flat array, row after row.
# ---------------------------------------------------------------------------
INT32_PTR = ctypes.POINTER(ctypes.c_int32)


def load(libname, symbol):
    path = os.path.join(BUILD, libname)
    if not os.path.exists(path):
        sys.exit(f"error: {path} not found. Run 'make' first.")
    func = getattr(ctypes.CDLL(path), symbol)
    func.argtypes = [INT32_PTR, INT32_PTR, INT32_PTR, ctypes.c_long, ctypes.c_long]
    func.restype = None
    return func


def as_c_array(arr):
    """View a Python array('i') as a C int32 array, without copying."""
    return (ctypes.c_int32 * len(arr)).from_buffer(arr)


def run_native(func, img, k):
    """Flatten the inputs, call the C/assembly function, return a flat output."""
    h, w = len(img), len(img[0])
    flat_img = array("i", [px for row in img for px in row])
    flat_k = array("i", [c for row in k for c in row])
    out = array("i", [-1]) * ((h - (KSIZE - 1)) * (w - (KSIZE - 1)))
    t0 = time.perf_counter()
    func(as_c_array(flat_img), as_c_array(out), as_c_array(flat_k), h, w)
    return out.tolist(), time.perf_counter() - t0


def run_python(img, k):
    t0 = time.perf_counter()
    out = conv_python(img, k)
    elapsed = time.perf_counter() - t0
    return [v for row in out for v in row], elapsed


# ---------------------------------------------------------------------------
def make_data(h, w, seed):
    """Deterministic test data: pixels 0..255, kernel coefficients -4..4."""
    rng = random.Random(seed)
    img = [[rng.randrange(256) for _ in range(w)] for _ in range(h)]
    k = [[rng.randrange(-4, 5) for _ in range(KSIZE)] for _ in range(KSIZE)]
    return img, k


def board_name():
    try:
        with open("/proc/device-tree/model") as f:
            return f.read().strip("\x00\n")
    except OSError:
        return "unknown board"


def benchmark(h, w, reps, seed, conv_c, conv_asm):
    img, k = make_data(h, w, seed)
    macs = (h - 2) * (w - 2) * KSIZE * KSIZE
    print(f"Board : {board_name()} ({platform.machine()}), Python {platform.python_version()}")
    print(f"Image : {h} x {w}, kernel 3 x 3, {macs / 1e6:.1f} M multiply-adds")
    print("Running Python (this is the slow one)...", flush=True)

    ref, t_py = run_python(img, k)
    rows = [("Python", t_py, True)]
    for name, func in (("C (gcc -O2)", conv_c), ("Assembly (NEON)", conv_asm)):
        times = []
        for _ in range(reps):
            out, t = run_native(func, img, k)
            times.append(t)
        rows.append((name, statistics.median(times), out == ref))

    print()
    print(f"{'version':<18} {'time (ms)':>12} {'vs Python':>11}  check")
    print("-" * 50)
    for name, t, ok in rows:
        print(f"{name:<18} {t * 1e3:>12.2f} {t_py / t:>10.1f}x  "
              f"{'OK' if ok else 'MISMATCH'}")
    print()
    print(f"C and assembly: median of {reps} runs. "
          f"'OK' means the output equals the Python output.")
    return all(ok for *_, ok in rows)


def self_test(conv_c, conv_asm):
    """Small and odd sizes exercise the loop limits and the NEON tail."""
    sizes = [(3, 3), (3, 4), (4, 3), (3, 7), (5, 5), (6, 9), (7, 10), (8, 8),
             (9, 11), (17, 9), (33, 65), (64, 67), (100, 131)]
    failures = 0
    for i, (h, w) in enumerate(sizes):
        img, k = make_data(h, w, seed=i)
        ref, _ = run_python(img, k)
        for name, func in (("C", conv_c), ("assembly", conv_asm)):
            out, _ = run_native(func, img, k)
            if out != ref:
                failures += 1
                print(f"MISMATCH  {name:<9} size {h} x {w}")
    print(f"{len(sizes)} sizes, C and assembly vs Python: "
          f"{'all OK' if failures == 0 else f'{failures} MISMATCH'}")
    return failures == 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--size", nargs=2, type=int, default=[2048, 2048], metavar=("H", "W"),
                   help="image height and width (default 2048 2048)")
    p.add_argument("--reps", type=int, default=5,
                   help="runs of C and assembly, the median is shown (default 5)")
    p.add_argument("--seed", type=int, default=2026, help="random seed for the data")
    p.add_argument("--test", action="store_true", help="correctness test on many sizes")
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this lab needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    if min(args.size) < KSIZE:
        sys.exit("error: the image must be at least 3 x 3")

    conv_c = load("libconv_c.so", "conv_c")
    conv_asm = load("libconv_asm.so", "conv_asm")
    if args.test:
        ok = self_test(conv_c, conv_asm)
    else:
        ok = benchmark(*args.size, args.reps, args.seed, conv_c, conv_asm)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
