#!/usr/bin/env python3
"""
conv_bench.py - the same 2D convolution in Python, C and ARM64 assembly.

Every version processes the same photo from the Raspberry Pi camera with an
edge-detection kernel. Each output is checked against the Python output, and
the time of each version is printed in one table.

    python3 conv_demo.py photo            # take the photo first (photo.pgm)
    python3 conv_bench.py                 # all versions on photo.pgm
    python3 conv_bench.py --skip-python   # skip Python, compare against C v1
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
PHOTO = "photo.pgm"           # the camera photo every part of the lab uses
PHOTO_SIZE = (2592, 1944)     # width x height: Python takes about 9 s on a Pi 5


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
    ("C v2 rows (yours)",   "libconv_student_c.so", "conv_c_rows"),
    ("ASM v1 brute (yours)", "libconv_student_v1.so", "conv_asm_v1"),
    ("ASM v2 pointers",     "libconv_asm.so",     "conv_asm_v2"),
    ("ASM v3 MAC (yours)",  "libconv_student.so", "conv_asm_v3"),
    ("ASM v4 NEON",         "libconv_asm.so",     "conv_asm_v4"),
]

# The versions students write in the notebook (Parts 3, 4 and 7).
YOURS = {"C v2 rows (yours)", "ASM v1 brute (yours)", "ASM v3 MAC (yours)"}

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
def make_data(h, w, seed):
    """Random test data for --test: pixels 0..255, kernel coefficients -4..4."""
    rng = random.Random(seed)
    k = [[rng.randrange(-4, 5) for _ in range(KSIZE)] for _ in range(KSIZE)]
    img = [[rng.randrange(256) for _ in range(w)] for _ in range(h)]
    return img, k


# The kernel of the lab: it detects edges. On a
# flat area the 9 products cancel out (8 * centre - 8 neighbours = 0); where
# the brightness changes, the result is large.
EDGE_KERNEL = [[-1, -1, -1],
               [-1,  8, -1],
               [-1, -1, -1]]


def read_pgm(path):
    """Read a binary grayscale PGM file (P5, 8-bit) into a list of rows."""
    with open(path, "rb") as f:
        data = f.read()
    fields, pos = [], 0
    while len(fields) < 4:                     # magic, width, height, maxval
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":          # skip a comment line
            pos = data.index(b"\n", pos) + 1
            continue
        end = pos
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(data[pos:end])
        pos = end
    if fields[0] != b"P5" or int(fields[3]) > 255:
        raise ValueError(f"{path}: not an 8-bit binary PGM (P5) file")
    w, h = int(fields[1]), int(fields[2])
    pixels = data[pos + 1:pos + 1 + w * h]
    return [list(pixels[r * w:(r + 1) * w]) for r in range(h)]


def write_pgm(path, rows):
    """Write a list of rows of 0..255 values as a binary grayscale PGM file."""
    h, w = len(rows), len(rows[0])
    with open(path, "wb") as f:
        f.write(f"P5\n{w} {h}\n255\n".encode())
        for row in rows:
            f.write(bytes(row))


NO_PHOTO = ("{} not found: take the photo with the camera first "
            "(Part 1 of lab.ipynb, or: python3 conv_demo.py photo).")


def load_photo(image=PHOTO):
    """The camera photo as a list of rows, or FileNotFoundError if missing."""
    if not os.path.exists(image):
        raise FileNotFoundError(NO_PHOTO.format(image))
    return read_pgm(image)


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


def benchmark(img, k, description, reps, skip_python):
    """Time every version on img with kernel k and print the table."""
    versions = load_versions()
    h, w = len(img), len(img[0])
    macs = (h - 2) * (w - 2) * KSIZE * KSIZE
    print(f"Board : {board_name()} ({platform.machine()}), Python {platform.python_version()}")
    print(f"Image : {w} x {h} ({description}), kernel 3 x 3, "
          f"{macs / 1e6:.1f} M multiply-adds")
    flat_img, flat_k = flatten(img, k)

    rows = []                                  # (name, seconds, status)
    if skip_python:
        base_name = "C v1"
        ref, _ = run_native(versions[0][1], flat_img, flat_k, h, w)
    else:
        base_name = "Python"
        print("Running Python (the slow one, about 9 seconds)...", flush=True)
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


def check_version(func, sizes):
    """True if func gives the Python result on every (h, w) in sizes."""
    for i, (h, w) in enumerate(sizes):
        img, k = make_data(h, w, seed=i)
        flat_img, flat_k = flatten(img, k)
        ref, _ = run_python(img, k)
        out, _ = run_native(func, flat_img, flat_k, h, w)
        if out != ref:
            return False
    return True


TEST_SIZES = [(3, 3), (3, 4), (4, 3), (3, 7), (5, 5), (6, 9), (7, 10), (8, 8),
              (9, 11), (17, 9), (33, 65), (64, 67), (100, 131)]


def self_test():
    """Small and odd sizes exercise the loop limits and the NEON tail.

    The versions students write are reported apart: before they write them,
    a MISMATCH there is expected and does not make the test fail."""
    failures = 0
    for name, func, error in load_versions():
        if func is None:
            status = f"NOT BUILT ({error})"
        elif check_version(func, TEST_SIZES):
            status = "OK"
        else:
            status = "MISMATCH"
        if name in YOURS:
            hint = "" if status == "OK" else "   <- expected until you write it in the notebook"
            print(f"  {name:<20} {status}{hint}")
        elif status != "OK":
            failures += 1
            print(f"  {name:<20} {status}")
    given = len(VERSIONS) - len(YOURS)
    print(f"{len(TEST_SIZES)} sizes x {given} given versions vs Python: "
          f"{'all OK' if failures == 0 else f'{failures} problems'}")
    return failures == 0


def check_yours():
    """Print 'OK <name>' or 'FAIL <name>' for each version students write.

    Run in a separate process (see conv_demo.run_race), so that a version
    that crashes cannot take the notebook down with it."""
    for name, func, _ in load_versions():
        if name in YOURS:
            ok = func is not None and check_version(func, [(9, 11), (17, 9)])
            print(("OK " if ok else "FAIL ") + name, flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reps", type=int, default=5,
                   help="runs of each C/assembly version, the median is shown (default 5)")
    p.add_argument("--image", metavar="FILE.pgm", default=PHOTO,
                   help=f"grayscale photo to process (default {PHOTO})")
    p.add_argument("--skip-python", action="store_true",
                   help="do not run Python; check and compare against C v1 instead")
    p.add_argument("--test", action="store_true", help="correctness test on many sizes")
    p.add_argument("--check-yours", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this lab needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    try:
        load(*VERSIONS[0][1:])                 # C is the reference: it must exist
    except RuntimeError as err:
        sys.exit(f"error: {err}")

    if args.check_yours:
        check_yours()
        return
    if args.test:
        ok = self_test()
    else:
        try:
            img = load_photo(args.image)
        except (OSError, ValueError) as err:
            sys.exit(f"error: {err}")
        if min(len(img), len(img[0])) < KSIZE:
            sys.exit("error: the image must be at least 3 x 3")
        description = f"photo {os.path.basename(args.image)}, edge-detection kernel"
        ok = benchmark(img, EDGE_KERNEL, description, args.reps, args.skip_python)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
