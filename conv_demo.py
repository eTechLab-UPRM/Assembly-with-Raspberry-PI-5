#!/usr/bin/env python3
"""
conv_demo.py - see the 2D convolution in the console.

    python3 conv_demo.py            # menu
    python3 conv_demo.py step       # the kernel sliding over a small image
    python3 conv_demo.py race       # Python, C and assembly running at once

Build the libraries first with "make". The console demo uses only the Python
standard library; lab.ipynb also uses notebook_step() and notebook_race().
"""
import argparse
import platform
import random
import sys
import threading
import time
from array import array

from conv_bench import (DEFAULT_SIZE, KSIZE, as_c_array, flatten, load, make_data,
                         run_python)

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
    img, k, out = step_example(seed=random.randrange(10**6))
    h, w = len(img), len(img[0])
    oh, ow = len(out), len(out[0])

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

    macs = (DEFAULT_SIZE - 2) ** 2 * 9
    print(f"\nThis {h} x {w} image needed {oh} x {ow} x 9 = {oh * ow * 9} "
          f"multiply-adds.\nThe {DEFAULT_SIZE} x {DEFAULT_SIZE} image of the race needs "
          f"{macs:,}: that is why the language matters.")
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
# 2. Race: Python, C and assembly v4 run at the same time on different cores.
# ---------------------------------------------------------------------------
BAR_WIDTH = 30
RACERS = ["Python", "C", "Assembly"]


def bar(fraction, width=BAR_WIDTH):
    filled = min(width, int(fraction * width))
    return "█" * filled + "░" * (width - filled)


def run_race(size, draw, interval=0.1):
    """Run the race and call draw(rows, elapsed) every `interval` seconds.

    rows is a list of (racer name, bar text, status text). Returns the final
    state: finish times, image counts and whether all outputs match.
    """
    conv_c = load("libconv_c.so", "conv_c_rows")
    conv_asm = load("libconv_asm.so", "conv_asm_v4")
    h = w = size
    img, k = make_data(h, w, seed=2026)
    flat_img, flat_k = flatten(img, k)
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)

    # finish: seconds each racer needed for its first image (None = running).
    # count: images C and assembly have finished so far.
    state = {"rows": 0, "done": False, "python": None, "outputs": {},
             "finish": dict.fromkeys(RACERS), "count": {"C": 0, "Assembly": 0}}

    def python_worker():
        t0 = time.perf_counter()
        out = [[0] * ow for _ in range(oh)]
        for y in range(oh):                    # same loops as conv_bench.py
            for x in range(ow):
                acc = 0
                for ky in range(KSIZE):
                    for kx in range(KSIZE):
                        acc += img[y + ky][x + kx] * k[ky][kx]
                out[y][x] = acc
            state["rows"] = y + 1
        state["finish"]["Python"] = time.perf_counter() - t0
        state["python"] = array("i", [v for row in out for v in row])
        state["done"] = True

    def native_worker(name, func):
        out = array("i", [0]) * (oh * ow)
        c_img, c_out, c_k = as_c_array(flat_img), as_c_array(out), as_c_array(flat_k)
        t0 = time.perf_counter()
        func(c_img, c_out, c_k, h, w)         # the race: one whole image
        state["finish"][name] = time.perf_counter() - t0
        state["count"][name] = 1
        while not state["done"]:              # then keep going until Python ends
            func(c_img, c_out, c_k, h, w)
            state["count"][name] += 1
        state["outputs"][name] = out

    def rows():
        result = []
        for name in RACERS:
            finish = state["finish"][name]
            if name == "Python":
                frac = state["rows"] / oh
            else:
                frac = 1.0 if finish is not None else 0.0
            status = f"{frac * 100:5.1f}%" if finish is None else f"done in {finish:.3f} s"
            if name != "Python" and state["count"][name]:
                status += f", {state['count'][name]} images so far"
            result.append((name, bar(frac), status))
        return result

    threads = [threading.Thread(target=python_worker, daemon=True),
               threading.Thread(target=native_worker, args=("C", conv_c), daemon=True),
               threading.Thread(target=native_worker, args=("Assembly", conv_asm),
                                daemon=True)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    while True:
        done = state["done"]                  # read before drawing: the last
        draw(rows(), time.perf_counter() - t0)  # frame then shows 100 %
        if done:
            break
        time.sleep(interval)
    for t in threads:
        t.join()
    state["ok"] = all(state["outputs"][n] == state["python"] for n in ("C", "Assembly"))
    return state


RACE_INTRO = ("All three start the same image at the same time, each on its own\n"
              "CPU core. Each bar is the progress of that one image. When C (v2,\n"
              "row order) and assembly (v4, NEON) finish, they keep going with\n"
              "more copies until Python is done.")


def race_summary(state):
    fin, count = state["finish"], state["count"]
    return [f"One image: Python {fin['Python']:.2f} s, C {fin['C']:.3f} s, "
            f"assembly {fin['Assembly']:.3f} s.",
            f"While Python did 1 image, C did {count['C']} and assembly did "
            f"{count['Assembly']}.",
            "All three versions produced the same output." if state["ok"]
            else "MISMATCH between versions!"]


def race_mode(size):
    """Console version of the race, drawn with ANSI escape codes."""
    print(CLEAR + BOLD + "RACE" + RESET + f"   preparing a {size} x {size} image...",
          flush=True)
    colors = {"Python": YELLOW, "C": CYAN, "Assembly": GREEN}
    first = [True]

    def draw(rows, elapsed):
        if first[0]:
            first[0] = False
            print(CLEAR + BOLD + "RACE" + RESET
                  + f"   {size} x {size} image, 3 x 3 kernel\n")
            print(RACE_INTRO + "\n")
            sys.stdout.write("\n" * 4 + HIDE_CURSOR)  # space for 3 bars + time
        lines = [f"{colors[n]}{n:<9}{RESET} {b} {s}" for n, b, s in rows]
        lines.append(f"{DIM}time: {elapsed:5.1f} s{RESET}")
        sys.stdout.write("\033[4F" + "".join(l + "\033[K\n" for l in lines))
        sys.stdout.flush()

    try:
        state = run_race(size, draw)
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + "\nRace stopped.\n")
        return
    sys.stdout.write(SHOW_CURSOR)
    first_line, second, check = race_summary(state)
    print(f"\n{BOLD}{first_line}{RESET}\n{second}")
    print((GREEN if state["ok"] else RED) + check + RESET)
    print(f"{DIM}For exact timings, one version at a time, run: "
          f"python3 conv_bench.py{RESET}")
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
# Jupyter notebook versions (lab.ipynb). IPython is imported only here, so
# the console demo keeps working with the standard library alone.
# ---------------------------------------------------------------------------
HTML_COLORS = {"Python": "#b58900", "C": "#268bd2", "Assembly": "#2aa198"}


def notebook_race(size=DEFAULT_SIZE):
    """The race inside a notebook cell, redrawn in place as HTML."""
    from html import escape
    from IPython.display import HTML, display

    print(RACE_INTRO)
    print(f"\nPreparing a {size} x {size} image...", flush=True)
    handle = display(HTML(""), display_id=True)

    def draw(rows, elapsed):
        lines = [f'<span style="color:{HTML_COLORS[n]};font-weight:bold">{n:<9}</span>'
                 f" {b} {escape(s)}" for n, b, s in rows]
        lines.append(f"time: {elapsed:5.1f} s")
        handle.update(HTML("<pre style='line-height:1.4'>" + "\n".join(lines) + "</pre>"))

    state = run_race(size, draw)
    print("\n".join(race_summary(state)))
    return state


def notebook_step(y, x, seed=4082):
    """Show how output pixel (y, x) of a small 6 x 8 example is computed."""
    from IPython.display import HTML, display

    img, k, out = step_example(seed)
    oh, ow = len(out), len(out[0])
    if not (0 <= y < oh and 0 <= x < ow):
        raise ValueError(f"y must be 0..{oh - 1} and x must be 0..{ow - 1}")

    def table(grid, highlight):
        cells = []
        for r, row in enumerate(grid):
            tds = "".join(
                f'<td style="padding:2px 8px;text-align:right;'
                f'{"background:#ffd54f;color:#000;font-weight:bold" if highlight(r, c) else ""}">'
                f"{v}</td>" for c, v in enumerate(row))
            cells.append(f"<tr>{tds}</tr>")
        return ('<table style="border-collapse:collapse;font-family:monospace;'
                'display:inline-table;margin-right:32px">' + "".join(cells) + "</table>")

    terms = " + ".join(f"{img[y + ky][x + kx]}·" + (f"({c})" if (c := k[ky][kx]) < 0 else f"{c}")
                       for ky in range(KSIZE) for kx in range(KSIZE))
    display(HTML(
        "<div><b>Input image</b> (the 3 x 3 window under the kernel is yellow)"
        "<br>" + table(img, lambda r, c: y <= r < y + KSIZE and x <= c < x + KSIZE)
        + table(k, lambda r, c: False) + "<b>Kernel</b></div>"
        f"<p style='font-family:monospace'>out[{y}][{x}] = {terms}<br>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= <b>{out[y][x]}</b></p>"
        "<b>Output image</b> (pixel (y, x) is yellow)<br>"
        + table(out, lambda r, c: (r, c) == (y, x))))


def step_example(seed):
    """A small deterministic example: 6 x 8 image, 3 x 3 kernel, its output."""
    rng = random.Random(seed)
    h, w = 6, 8
    img = [[rng.randrange(10) for _ in range(w)] for _ in range(h)]
    k = [[rng.randrange(-1, 3) for _ in range(KSIZE)] for _ in range(KSIZE)]
    out, _ = run_python(img, k)
    ow = w - 2
    return img, k, [list(out[r * ow:(r + 1) * ow]) for r in range(h - 2)]


# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", choices=["step", "race"],
                   help="go straight to one mode instead of the menu")
    p.add_argument("--size", type=int, default=DEFAULT_SIZE,
                   help=f"image size for the race (default {DEFAULT_SIZE})")
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this lab needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    try:
        load("libconv_c.so", "conv_c_rows")
        load("libconv_asm.so", "conv_asm_v4")
    except RuntimeError as err:
        sys.exit(f"error: {err}")
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
            race_mode(args.size)
        if args.mode:
            break
    print(SHOW_CURSOR, end="")


if __name__ == "__main__":
    main()
