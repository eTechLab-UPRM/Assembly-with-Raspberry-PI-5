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

from conv_bench import (DEFAULT_SIZE, EDGE_KERNEL, KSIZE, as_c_array, flatten, load,
                         load_image, load_versions, make_data, read_pgm, run_native,
                         run_python, write_pgm)

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
# 2. Race: Python and every C/assembly version run at the same time.
# ---------------------------------------------------------------------------
BAR_WIDTH = 30
SCALE_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def bar(fraction, width=BAR_WIDTH):
    filled = min(width, int(fraction * width))
    return "█" * filled + "░" * (width - filled)


def short_name(name):
    """'ASM v3 MAC (yours)' -> 'ASM v3', 'C v1 column order' -> 'C v1'."""
    return " ".join(name.split()[:2])


def run_race(size, draw, interval=0.1, image=None):
    """Run the race and call draw(panel1, panel2, per_char, elapsed) repeatedly.

    panel1: [(name, fraction, status)] progress of ONE image for every racer.
    panel2: [(name, fraction, count)] images each C/assembly version has
            finished while Python works; a full bar is per_char * BAR_WIDTH
            images, so each bar character is worth per_char images.
    Returns the final state: finish times, image counts, outputs check.
    """
    natives = [(short_name(n), f) for n, f, _ in load_versions() if f is not None]
    img, k, _ = load_image(image, size)        # a photo, or the random image
    h, w = len(img), len(img[0])
    flat_img, flat_k = flatten(img, k)
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)
    names = ["Python"] + [n for n, _ in natives]

    # finish: seconds each racer needed for its first image (None = running).
    # count: images each C/assembly version has finished so far.
    state = {"rows": 0, "done": False, "python": None, "outputs": {},
             "finish": dict.fromkeys(names), "count": {n: 0 for n, _ in natives}}

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

    def panels():
        panel1 = []
        for name in names:
            finish = state["finish"][name]
            if name == "Python":
                frac = state["rows"] / oh
            else:
                frac = 1.0 if finish is not None else 0.0
            status = f"{frac * 100:5.1f}%" if finish is None else f"done in {finish:.3f} s"
            panel1.append((name, frac, status))
        most = max(state["count"].values(), default=0)
        per_char = next((s for s in SCALE_STEPS if most <= s * BAR_WIDTH), SCALE_STEPS[-1])
        panel2 = [(n, c / (per_char * BAR_WIDTH), c) for n, c in state["count"].items()]
        return panel1, panel2, per_char

    threads = [threading.Thread(target=python_worker, daemon=True)]
    threads += [threading.Thread(target=native_worker, args=nf, daemon=True) for nf in natives]
    # C/assembly threads need Python's lock for a moment after each image;
    # a short switch interval keeps them from waiting behind the Python loop.
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.0005)
    try:
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        while True:
            done = state["done"]                  # read before drawing: the last
            draw(*panels(), time.perf_counter() - t0)  # frame then shows 100 %
            if done:
                break
            time.sleep(interval)
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)
    state["ok"] = all(state["outputs"][n] == state["python"] for n, _ in natives)
    return state


RACE_INTRO = (
    "Python and every C and assembly version start the same image at the same\n"
    "time. Panel 1 is the progress of that one image. Panel 2 counts how many\n"
    "times each C and assembly version finishes the image while Python works\n"
    "on its first one. The 7 versions share the 4 CPU cores of the Pi, so\n"
    "compare them with each other; exact times come from conv_bench.py.")
PANEL2_TITLE = "Images finished while Python works on one (each █ = {} images)"
PANEL2_TITLE_HTML = "Images finished while Python works on one (full bar = {} images)"


def race_summary(state):
    fin, count = state["finish"], state["count"]
    best = max(count, key=count.get)
    return ([f"Python needed {fin['Python']:.2f} s for one image. Meanwhile:"]
            + [f"  {n:<7} finished {c:5d} images" for n, c in count.items()]
            + [f"Fastest: {best}.",
               "All versions produced the same output." if state["ok"]
               else "MISMATCH between versions!"])


def race_color(name):
    return YELLOW if name == "Python" else CYAN if name.startswith("C") else GREEN


def race_mode(size, image=None):
    """Console version of the race, drawn with ANSI escape codes."""
    what = image or f"a {size} x {size} image"
    print(CLEAR + BOLD + "RACE" + RESET + f"   preparing {what}...", flush=True)
    drawn = [0]                                    # lines drawn by the last frame

    def draw(panel1, panel2, per_char, elapsed):
        if not drawn[0]:
            print(CLEAR + BOLD + "RACE" + RESET + f"   {what}, 3 x 3 kernel\n")
            print(RACE_INTRO + "\n")
            sys.stdout.write(HIDE_CURSOR)
        lines = [BOLD + "1. One image" + RESET]
        lines += [f"{race_color(n)}{n:<9}{RESET} {bar(f)} {s}" for n, f, s in panel1]
        lines += ["", BOLD + "2. " + PANEL2_TITLE.format(per_char) + RESET]
        lines += [f"{race_color(n)}{n:<9}{RESET} {bar(f)} {c:5d}" for n, f, c in panel2]
        lines += [f"{DIM}time: {elapsed:5.1f} s{RESET}"]
        up = f"\033[{drawn[0]}F" if drawn[0] else ""
        sys.stdout.write(up + "".join(l + "\033[K\n" for l in lines))
        sys.stdout.flush()
        drawn[0] = len(lines)

    try:
        state = run_race(size, draw, image=image)
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + "\nRace stopped.\n")
        return
    sys.stdout.write(SHOW_CURSOR)
    *lines, check = race_summary(state)
    print("\n" + BOLD + lines[0] + RESET)
    print("\n".join(lines[1:]))
    print((GREEN if state["ok"] else RED) + check + RESET)
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
# Jupyter notebook versions (lab.ipynb). IPython is imported only here, so
# the console demo keeps working with the standard library alone.
# ---------------------------------------------------------------------------
def html_color(name):
    return "#b58900" if name == "Python" else "#268bd2" if name.startswith("C") else "#2aa198"


def notebook_race(image=None, size=DEFAULT_SIZE):
    """The race inside a notebook cell, redrawn in place as HTML.

    image: a photo from take_photo(), or None for the random image.
    """
    from html import escape
    from IPython.display import HTML, display

    print(RACE_INTRO)
    print(f"\nPreparing {image or f'a {size} x {size} image'}...", flush=True)
    handle = display(HTML(""), display_id=True)

    def row(name, frac, text):
        color = html_color(name)
        return (f'<tr><td style="color:{color};font-weight:bold;padding:2px 12px 2px 0;text-align:left">'
                f"{name}</td>"
                f'<td style="width:300px;padding:2px 0"><div style="background:#ddd;'
                f'height:14px"><div style="background:{color};height:14px;'
                f'width:{min(frac, 1) * 100:.1f}%"></div></div></td>'
                f'<td style="padding:2px 12px;font-family:monospace">{escape(text)}</td></tr>')

    def draw(panel1, panel2, per_char, elapsed):
        html = ["<b>1. One image</b><table style='border-collapse:collapse'>"]
        html += [row(n, f, s) for n, f, s in panel1]
        html += ["</table><br><b>2. " + escape(PANEL2_TITLE_HTML.format(per_char * BAR_WIDTH))
                 + "</b>"
                 "<table style='border-collapse:collapse'>"]
        html += [row(n, f, f"{c} images") for n, f, c in panel2]
        html += [f"</table><p style='font-family:monospace'>time: {elapsed:5.1f} s</p>"]
        handle.update(HTML("".join(html)))

    state = run_race(size, draw, image=image)
    print("\n".join(race_summary(state)))
    return state


def png_gray(rows):
    """Encode a list of rows of 0..255 values as a grayscale PNG (bytes)."""
    import struct
    import zlib

    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(r) for r in rows)    # filter 0 on every row

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def html_picture(rows, title, scale=2):
    """An <img> of a grayscale image (rows of 0..255), drawn scale times larger."""
    import base64

    data = base64.b64encode(png_gray(rows)).decode()
    return (f'<div style="display:inline-block;margin-right:24px;vertical-align:top">'
            f"<b>{title}</b><br><img src='data:image/png;base64,{data}' "
            f"style='width:{scale * len(rows[0])}px;image-rendering:pixelated'></div>")


def html_numbers(rows, title, gray=True):
    """A table of numbers, each cell shaded with its own gray level."""
    cells = []
    for r in rows:
        tds = []
        for v in r:
            shade = (f"background:rgb({v},{v},{v});color:{'#000' if v > 127 else '#fff'};"
                     if gray else "")
            tds.append(f'<td style="{shade}padding:3px 6px;text-align:right">{v}</td>')
        cells.append("<tr>" + "".join(tds) + "</tr>")
    return (f'<div style="display:inline-block;margin-right:24px;vertical-align:top">'
            f"<b>{title}</b><table style='border-collapse:collapse;font-family:monospace'>"
            + "".join(cells) + "</table></div>")


def notebook_image(image=None, size=DEFAULT_SIZE, crop=200, zoom=8):
    """Show the input image, the kernel and the output image in the notebook.

    image=None: the benchmark's random image (its top-left corner, since the
    whole image is just noise). image="photo.pgm": a photo from take_photo(),
    shown whole, with the edge-detection kernel.
    """
    from IPython.display import HTML, display

    if image:
        display(HTML(photo_html(image, zoom)))
        return

    crop = min(crop, size - (KSIZE - 1))
    zoom = min(zoom, crop)
    img, k = make_data(size, size, seed=2026, rows=crop + KSIZE - 1)
    window = [row[:crop + KSIZE - 1] for row in img]
    out, _ = run_python(window, k)
    out = [list(out[r * crop:(r + 1) * crop]) for r in range(crop)]
    low = min(min(r) for r in out)
    high = max(max(r) for r in out)
    out_gray = [[(v - low) * 255 // (high - low or 1) for v in r] for r in out]

    total = size * size
    display(HTML(
        f"<p>The full input image is <b>{size} × {size} = {total:,} pixels</b> "
        f"({total * 4 / 1e6:.0f} MB as 32-bit integers), each a random number from 0 "
        f"(black) to 255 (white), always the same ones (fixed seed). It looks like TV "
        f"static because it is random. Below: its top-left {crop} × {crop} corner, "
        f"drawn twice as large.</p>"
        + html_picture([r[:crop] for r in window[:crop]], f"Input (top-left {crop} × {crop})")
        + html_numbers([r[:zoom] for r in window[:zoom]], f"Zoom: top-left {zoom} × {zoom} pixels")
        + html_numbers(k, "Kernel", gray=False)
        + html_picture(out_gray, f"Output (same corner, {low} → black, {high} → white)")))


def photo_html(image, zoom=8, width=480):
    """HTML with a photo, a zoom on its centre, the edge kernel and the edges.

    The convolution runs on the whole photo with the C version (it takes a
    fraction of a second); both images are then shrunk to `width` pixels to
    fit on the screen.
    """
    img = read_pgm(image)
    h, w = len(img), len(img[0])
    flat_img, flat_k = flatten(img, EDGE_KERNEL)
    out, t = run_native(load("libconv_c.so", "conv_c_rows"), flat_img, flat_k, h, w)
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)

    f = max(1, -(-w // width))                 # shrink factor, rounded up
    small_in = [row[::f] for row in img[::f]]
    # Edges are thin lines: keep the strongest edge of each f x f block, so
    # they do not disappear when the image is shrunk.
    small_out = []
    for r0 in range(0, oh - f + 1, f):
        block_rows = [out[(r0 + i) * ow:(r0 + i + 1) * ow] for i in range(f)]
        small_out.append([max(abs(v) for row in block_rows for v in row[c0:c0 + f])
                          for c0 in range(0, ow - f + 1, f)])
    values = sorted(v for row in small_out for v in row)
    top = values[int(len(values) * 0.99)] or 1     # ignore the brightest 1 %
    edges = [[255 - min(255, v * 255 // top) for v in row] for row in small_out]

    cy, cx = h // 2 - zoom // 2, w // 2 - zoom // 2
    centre = [row[cx:cx + zoom] for row in img[cy:cy + zoom]]
    return (f"<p>Your photo: <b>{w} × {h} = {w * h:,} pixels</b>, each a number from 0 "
            f"(black) to 255 (white). The edge-detection kernel gives 0 where the "
            f"brightness does not change, and a large value at edges. The C version "
            f"(row order) computed all {oh * ow:,} output pixels in {t * 1e3:.0f} ms.</p>"
            + html_picture(small_in, "Input photo", scale=1)
            + html_picture(edges, "Output: edges (dark = strong edge)", scale=1)
            + "<br>"
            + html_numbers(centre, f"Zoom: {zoom} × {zoom} pixels at the centre")
            + html_numbers(EDGE_KERNEL, "Edge-detection kernel", gray=False))


def take_photo(path="photo.pgm", width=2592, height=1944, seconds=3):
    """Take a grayscale photo with the Raspberry Pi camera and save it as PGM.

    A preview window shows the camera for `seconds` seconds before the shot.
    Returns the file name, or None if there is no camera (the lab then keeps
    using the random image). 2592 x 1944 is the full resolution of the
    Camera Module v1; other modules are scaled to the same size.
    """
    import os
    import shutil
    import subprocess

    if not shutil.which("rpicam-still"):
        print("rpicam-still is not installed: no camera support. "
              "The lab will use the random image.")
        return None
    raw = path + ".yuv"
    cmd = ["rpicam-still", "-t", str(seconds * 1000), "--encoding", "yuv420",
           "--width", str(width), "--height", str(height), "-o", raw]
    print(f"Look at the camera: taking the photo in {seconds} seconds...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:                 # no screen (e.g. over SSH): no preview
        result = subprocess.run(cmd + ["-n"], capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(raw):
        last = (result.stderr.strip().splitlines() or ["unknown error"])[-1]
        print(f"The camera did not take the photo ({last}). "
              "Check the cable, reboot, and try again. The lab will use the random image.")
        return None

    # YUV420: first the brightness (Y) of every pixel, which is exactly the
    # grayscale image, then the colour planes, which we do not need. Each row
    # of Y can be padded to `stride` bytes.
    with open(raw, "rb") as fh:
        data = fh.read()
    os.remove(raw)
    stride = len(data) * 2 // (3 * height)
    rows = [list(data[r * stride:r * stride + width]) for r in range(height)]
    write_pgm(path, rows)
    print(f"Saved {path}: {width} x {height} pixels, grayscale.")
    return path


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
    p.add_argument("--image", metavar="FILE.pgm",
                   help="race on this photo (see take_photo) instead of the random image")
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
            race_mode(args.size, args.image)
        if args.mode:
            break
    print(SHOW_CURSOR, end="")


if __name__ == "__main__":
    main()
