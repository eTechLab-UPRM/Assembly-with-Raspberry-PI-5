#!/usr/bin/env python3
"""
conv_bench.py - the same 2D convolution in Python, C and ARM64 assembly.

Every version gets the same image and kernel. Each output is checked against
the Python output, and the time of each version is printed in one table.

    python3 conv_bench.py                 # 2400 x 2400 image, all versions
    python3 conv_bench.py --skip-python   # skip Python, compare against C v1
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
DEFAULT_SIZE = 2400          # Python takes about 10 s on a Raspberry Pi 5


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
# C and assembly versions, loaded from build/*.so with ctypes. All of them
# have the C signature
#   void f(const int32_t *in, int32_t *out, const int32_t *k, long h, long w)
# and take the image as one flat array, row after row.
# ---------------------------------------------------------------------------
VERSIONS = [
    # (name in the table,   library,              function)
    ("C v1 column order",   "libconv_c.so",       "conv_c_cols"),
    ("C v2 row order",      "libconv_c.so",       "conv_c_rows"),
    ("ASM v1 brute force",  "libconv_asm.so",     "conv_asm_v1"),
    ("ASM v2 pointers",     "libconv_asm.so",     "conv_asm_v2"),
    ("ASM v3 MAC (yours)",  "libconv_student.so", "conv_asm_v3"),
    ("ASM v4 NEON",         "libconv_asm.so",     "conv_asm_v4"),
]

INT32_PTR = ctypes.POINTER(ctypes.c_int32)


def load(libname, symbol):
    """Return the C/assembly function, or raise RuntimeError if it is missing."""
    path = os.path.join(BUILD, libname)
    if not os.path.exists(path):
        raise RuntimeError(f"{path} not found. Run 'make' and fix any error it shows.")
    try:
        func = getattr(ctypes.CDLL(path), symbol)
    except AttributeError:
        raise RuntimeError(f"function {symbol} not found in {path}.") from None
    func.argtypes = [INT32_PTR, INT32_PTR, INT32_PTR, ctypes.c_long, ctypes.c_long]
    func.restype = None
    return func


def as_c_array(arr):
    """View a Python array('i') as a C int32 array, without copying."""
    return (ctypes.c_int32 * len(arr)).from_buffer(arr)


def flatten(img, k):
    """Lists of lists -> flat int32 arrays, the layout C and assembly expect."""
    return (array("i", [px for row in img for px in row]),
            array("i", [c for row in k for c in row]))


def run_native(func, flat_img, flat_k, h, w):
    """Call one C/assembly version, return (flat output, seconds)."""
    out = array("i", [-1]) * ((h - (KSIZE - 1)) * (w - (KSIZE - 1)))
    c_img, c_out, c_k = as_c_array(flat_img), as_c_array(out), as_c_array(flat_k)
    t0 = time.perf_counter()
    func(c_img, c_out, c_k, h, w)
    return out, time.perf_counter() - t0


def run_python(img, k):
    """Run the Python version, return (flat output, seconds)."""
    t0 = time.perf_counter()
    out = conv_python(img, k)
    elapsed = time.perf_counter() - t0
    return array("i", [v for row in out for v in row]), elapsed


# ---------------------------------------------------------------------------
def make_data(h, w, seed, rows=None):
    """Deterministic test data: pixels 0..255, kernel coefficients -4..4.

    With rows=N only the first N rows of the image are generated (they are
    identical to the first N rows of the full image), for previews.
    """
    rng = random.Random(seed)
    k = [[rng.randrange(-4, 5) for _ in range(KSIZE)] for _ in range(KSIZE)]
    img = [[rng.randrange(256) for _ in range(w)] for _ in range(h if rows is None else rows)]
    return img, k


def board_name():
    try:
        with open("/proc/device-tree/model") as f:
            return f.read().strip("\x00\n")
    except OSError:
        return "unknown board"


def load_versions():
    """[(name, function or None, error message)] for every native version."""
    loaded = []
    for name, lib, symbol in VERSIONS:
        try:
            loaded.append((name, load(lib, symbol), ""))
        except RuntimeError as err:
            loaded.append((name, None, str(err)))
    return loaded


def benchmark(h, w, reps, seed, skip_python):
    versions = load_versions()
    macs = (h - 2) * (w - 2) * KSIZE * KSIZE
    print(f"Board : {board_name()} ({platform.machine()}), Python {platform.python_version()}")
    print(f"Image : {h} x {w}, kernel 3 x 3, {macs / 1e6:.1f} M multiply-adds")
    print("Preparing the data...", flush=True)
    img, k = make_data(h, w, seed)
    flat_img, flat_k = flatten(img, k)

    rows = []                                  # (name, seconds, status)
    if skip_python:
        base_name = "C v1"
        ref, _ = run_native(versions[0][1], flat_img, flat_k, h, w)
    else:
        base_name = "Python"
        print("Running Python (the slow one, about 10 seconds)...", flush=True)
        ref, t_py = run_python(img, k)
        rows.append(("Python", t_py, "OK"))
    print("Running C and assembly...", flush=True)

    for name, func, error in versions:
        if func is None:
            rows.append((name, None, "NOT BUILT"))
            print(f"  {name}: {error}")
            continue
        times = []
        for _ in range(reps):
            out, t = run_native(func, flat_img, flat_k, h, w)
            times.append(t)
        rows.append((name, statistics.median(times), "OK" if out == ref else "MISMATCH"))

    base_t = rows[0][1]
    print()
    print(f"{'version':<20} {'time (ms)':>11} {'vs ' + base_name:>11}  check")
    print("-" * 52)
    for name, t, status in rows:
        if t is None:
            print(f"{name:<20} {'-':>11} {'-':>11}  {status}")
        else:
            print(f"{name:<20} {t * 1e3:>11.2f} {base_t / t:>10.1f}x  {status}")
    print()
    print(f"C and assembly: median of {reps} runs. "
          f"'OK' means the output equals the {base_name} output.")
    return all(status == "OK" for *_, status in rows)


def self_test():
    """Small and odd sizes exercise the loop limits and the NEON tail."""
    versions = load_versions()
    sizes = [(3, 3), (3, 4), (4, 3), (3, 7), (5, 5), (6, 9), (7, 10), (8, 8),
             (9, 11), (17, 9), (33, 65), (64, 67), (100, 131)]
    failures = 0
    for name, func, error in versions:
        if func is None:
            failures += 1
            print(f"NOT BUILT {name}: {error}")
    for i, (h, w) in enumerate(sizes):
        img, k = make_data(h, w, seed=i)
        flat_img, flat_k = flatten(img, k)
        ref, _ = run_python(img, k)
        for name, func, _ in versions:
            if func is None:
                continue
            out, _ = run_native(func, flat_img, flat_k, h, w)
            if out != ref:
                failures += 1
                print(f"MISMATCH  {name:<20} size {h} x {w}")
    print(f"{len(sizes)} sizes x {len(versions)} versions vs Python: "
          f"{'all OK' if failures == 0 else f'{failures} problems'}")
    return failures == 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--size", nargs=2, type=int, default=[DEFAULT_SIZE] * 2, metavar=("H", "W"),
                   help=f"image height and width (default {DEFAULT_SIZE} {DEFAULT_SIZE})")
    p.add_argument("--reps", type=int, default=5,
                   help="runs of each C/assembly version, the median is shown (default 5)")
    p.add_argument("--seed", type=int, default=2026, help="random seed for the data")
    p.add_argument("--skip-python", action="store_true",
                   help="do not run Python; check and compare against C v1 instead")
    p.add_argument("--test", action="store_true", help="correctness test on many sizes")
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this lab needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    if min(args.size) < KSIZE:
        sys.exit("error: the image must be at least 3 x 3")
    try:
        load(*VERSIONS[0][1:])                 # C is the reference: it must exist
    except RuntimeError as err:
        sys.exit(f"error: {err}")

    if args.test:
        ok = self_test()
    else:
        ok = benchmark(*args.size, args.reps, args.seed, args.skip_python)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
