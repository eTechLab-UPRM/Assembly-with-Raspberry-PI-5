#!/usr/bin/env python3
"""
conv_demo.py - see the 2D convolution in the console.

    python3 conv_demo.py            # menu
    python3 conv_demo.py step       # the kernel sliding over a small image
    python3 conv_demo.py race       # Python, C and assembly running at once

Build the libraries first with "make". Only the Python standard library is used.
"""
import argparse
import math
import platform
import random
import sys
import threading
import time
from array import array

from conv_bench import KSIZE, as_c_array, conv_python, load, make_data, run_python

# ANSI escape codes for colors and cursor movement.
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
YELLOW, GREEN, CYAN, RED = "\033[33m", "\033[32m", "\033[36m", "\033[31m"
HIGHLIGHT = "\033[30;43m"          # black text on a yellow background
CLEAR = "\033[H\033[2J"           # clear the screen
HIDE_CURSOR, SHOW_CURSOR = "\033[?25l", "\033[?25h"


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


# ---------------------------------------------------------------------------
# 1. Step by step: the kernel slides over a small grid of numbers.
# ---------------------------------------------------------------------------
def show_step(img, k, out, y, x):
    h, w = len(img), len(img[0])
    oh, ow = len(out), len(out[0])
    print(CLEAR + BOLD + "STEP BY STEP" + RESET
          + f"   output pixel ({y}, {x}) of {oh} x {ow}\n")

    print(f"{'Input image':<{4 * w + 6}}Kernel")
    for r in range(h):
        line = ""
        for c in range(w):
            cell = f"{img[r][c]:>3} "
            inside = y <= r < y + KSIZE and x <= c < x + KSIZE
            line += HIGHLIGHT + cell + RESET if inside else cell
        if r < KSIZE:
            line += "      " + CYAN + "".join(f"{v:>3} " for v in k[r]) + RESET
        print(line)

    terms = [f"{img[y + ky][x + kx]}*" + (f"({c})" if (c := k[ky][kx]) < 0 else f"{c}")
             for ky in range(KSIZE) for kx in range(KSIZE)]
    print(f"\nout[{y}][{x}] = " + " + ".join(terms))
    print(f"          = {BOLD}{GREEN}{out[y][x]}{RESET}"
          f"   (9 multiplications and 9 additions)\n")

    print("Output image")
    for r in range(oh):
        line = ""
        for c in range(ow):
            if (r, c) == (y, x):
                line += BOLD + GREEN + f"{out[r][c]:>5}" + RESET
            elif (r, c) < (y, x):
                line += f"{out[r][c]:>5}"
            else:
                line += DIM + "    ." + RESET
        print(line)


def step_mode():
    rng = random.Random()
    h, w = 6, 8
    img = [[rng.randrange(10) for _ in range(w)] for _ in range(h)]
    k = [[rng.randrange(-1, 3) for _ in range(KSIZE)] for _ in range(KSIZE)]
    out, _ = run_python(img, k)
    oh, ow = h - 2, w - 2
    out = [out[r * ow:(r + 1) * ow] for r in range(oh)]

    auto = False
    for y in range(oh):
        for x in range(ow):
            show_step(img, k, out, y, x)
            if auto:
                time.sleep(0.6)
                continue
            key = ask(f"\n{DIM}[Enter] next pixel   [a] auto   [q] back to menu{RESET} ")
            if key == "q":
                return
            auto = key == "a"

    macs = (2048 - 2) * (2048 - 2) * 9
    print(f"\nThis {h} x {w} image needed {oh} x {ow} x 9 = {oh * ow * 9} "
          f"multiply-adds.\nThe 2048 x 2048 image of the race needs "
          f"{macs:,}: that is why the language matters.")
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
# 2. Race: all three versions run at the same time on different CPU cores.
# ---------------------------------------------------------------------------
BAR_WIDTH = 40


def bar(fraction, width=BAR_WIDTH):
    filled = min(width, int(fraction * width))
    return "█" * filled + "░" * (width - filled)


def race_mode(conv_c, conv_asm, size):
    h = w = size
    print(CLEAR + BOLD + "RACE" + RESET + f"   preparing a {h} x {w} image...",
          flush=True)
    img, k = make_data(h, w, seed=2026)
    flat_img = array("i", [px for row in img for px in row])
    flat_k = array("i", [c for row in k for c in row])
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)

    # Fixed bar scale: estimate how many images C and assembly will finish
    # while Python does one, so the bars never rescale during the race.
    probe = array("i", [0]) * (oh * ow)
    native_t = []
    for func in (conv_c, conv_asm):
        best = float("inf")
        for _ in range(2):                    # the first call can be slower
            t = time.perf_counter()
            func(as_c_array(flat_img), as_c_array(probe), as_c_array(flat_k), h, w)
            best = min(best, time.perf_counter() - t)
        native_t.append(best)
    rows = min(16, oh)
    t = time.perf_counter()
    conv_python(img[:rows + KSIZE - 1], k)
    python_t = (time.perf_counter() - t) * oh / rows
    expected = python_t / min(native_t)
    per_char = max(1, math.ceil(expected * 1.25 / BAR_WIDTH))

    state = {"rows": 0, "done": False, "python": None,
             "C": 0, "Assembly": 0, "outputs": {}}

    def python_worker():
        out = [[0] * ow for _ in range(oh)]
        for y in range(oh):                    # same loops as conv_bench.py
            for x in range(ow):
                acc = 0
                for ky in range(KSIZE):
                    for kx in range(KSIZE):
                        acc += img[y + ky][x + kx] * k[ky][kx]
                out[y][x] = acc
            state["rows"] = y + 1
        state["python"] = [v for row in out for v in row]
        state["done"] = True

    def native_worker(name, func):
        out = array("i", [0]) * (oh * ow)
        c_img, c_out, c_k = as_c_array(flat_img), as_c_array(out), as_c_array(flat_k)
        while not state["done"]:
            func(c_img, c_out, c_k, h, w)     # one whole image per call
            state[name] += 1
        state["outputs"][name] = out.tolist()

    threads = [threading.Thread(target=python_worker, daemon=True),
               threading.Thread(target=native_worker, args=("C", conv_c), daemon=True),
               threading.Thread(target=native_worker, args=("Assembly", conv_asm),
                                daemon=True)]

    print(CLEAR + BOLD + "RACE" + RESET
          + f"   {h} x {w} image, 3 x 3 kernel, each version on its own CPU core\n")
    print(f"Python works on ONE image. Meanwhile, C and assembly process the "
          f"same image\nagain and again: how many times can they finish it?\n")
    print(f"{DIM}Python bar: progress of its one image.  "
          f"C and assembly bars: each █ = {per_char} images.{RESET}\n")
    print("\n\n\n")                              # space for the 3 bars
    sys.stdout.write(HIDE_CURSOR)
    t0 = time.perf_counter()
    for t in threads:
        t.start()

    try:
        while True:
            elapsed = time.perf_counter() - t0
            frac = state["rows"] / oh
            lines = [
                f"{YELLOW}Python   {RESET} {bar(frac)} {frac * 100:5.1f}% of 1 image",
                f"{CYAN}C        {RESET} {bar(state['C'] / (per_char * BAR_WIDTH))} {state['C']:5d} images",
                f"{GREEN}Assembly {RESET} {bar(state['Assembly'] / (per_char * BAR_WIDTH))} "
                f"{state['Assembly']:5d} images",
                f"{DIM}time: {elapsed:5.1f} s{RESET}",
            ]
            sys.stdout.write("\033[4F" + "".join(l + "\033[K\n" for l in lines))
            sys.stdout.flush()
            if state["done"]:
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + "\nRace stopped.\n")
        return
    sys.stdout.write(SHOW_CURSOR)

    for t in threads:
        t.join()
    ok = all(state["outputs"][n] == state["python"] for n in ("C", "Assembly"))
    print(f"\n{BOLD}While Python finished 1 image, C finished {state['C']} "
          f"and assembly finished {state['Assembly']}.{RESET}")
    print((GREEN + "All three versions produced the same output."
           if ok else RED + "MISMATCH between versions!") + RESET)
    print(f"{DIM}For exact timings, one version at a time, run: "
          f"python3 conv_bench.py{RESET}")
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", choices=["step", "race"],
                   help="go straight to one mode instead of the menu")
    p.add_argument("--size", type=int, default=2048,
                   help="image size for the race (default 2048)")
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this lab needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    conv_c = load("libconv_c.so", "conv_c")
    conv_asm = load("libconv_asm.so", "conv_asm")
    modes = {"1": "step", "2": "race"}

    choice = args.mode
    while True:
        if not args.mode:
            print(CLEAR + BOLD + "2D CONVOLUTION: Python -> C -> Assembly" + RESET + "\n")
            print("  1) Step by step   how a convolution works")
            print("  2) Race           how fast each language does it")
            print("  q) Quit")
            key = ask("\n> ")
            if key == "q":
                break
            choice = modes.get(key)
        if choice == "step":
            step_mode()
        elif choice == "race":
            race_mode(conv_c, conv_asm, args.size)
        if args.mode:
            break
    print(SHOW_CURSOR, end="")


if __name__ == "__main__":
    main()
