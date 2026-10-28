#!/usr/bin/env python3
"""
conv_demo.py - see the 2D convolution, in the console or in project.ipynb.

    python3 conv_demo.py            # menu
    python3 conv_demo.py step       # the kernel sliding over a small image
    python3 conv_demo.py photo      # take the camera photo (photo.pgm)
    python3 conv_demo.py race       # Python vs. every C and assembly version

Build the libraries first with "make". The console demo uses only the Python
standard library; project.ipynb also uses notebook_step(), take_photo(),
notebook_image(), build_c_v2(), build_v1(), build_v3() and notebook_race().
"""
import argparse
import os
import platform
import random
import sys
import threading
import time
from array import array

from conv_bench import (EDGE_KERNEL, KSIZE, NO_PHOTO, PHOTO, PHOTO_SIZE, YOURS, as_c_array,
                        flatten, load, load_photo, load_versions, run_native, run_python,
                        short_name, write_pgm)

HERE = os.path.dirname(os.path.abspath(__file__))   # the project folder

# ANSI escape codes for colors and cursor movement.
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
YELLOW, GREEN, CYAN, RED = "\033[33m", "\033[32m", "\033[36m", "\033[31m"
HIGHLIGHT = "\033[30;43m"          # black text on a yellow background
CLEAR = "\033[H\033[2J"           # clear the screen
HIDE_CURSOR, SHOW_CURSOR = "\033[?25l", "\033[?25h"


class LabError(Exception):
    """An error with a message for the student. In Jupyter it shows only the
    message, without the Python traceback."""

    def _render_traceback_(self):
        return [RED + BOLD + "ERROR" + RESET] + [RED + line + RESET
                                                 for line in str(self).splitlines()]


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

    pw, ph = PHOTO_SIZE
    macs = (pw - 2) * (ph - 2) * 9
    print(f"\nThis {h} x {w} image needed {oh} x {ow} x 9 = {oh * ow * 9} "
          f"multiply-adds.\nThe {pw} x {ph} camera photo needs {macs:,}: "
          f"that is why the language matters.")
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


# ---------------------------------------------------------------------------
# 2. The camera photo: every part of the project uses it.
# ---------------------------------------------------------------------------
NO_CAMERA = """No camera detected. Check the camera connection:
  1. Shut the Raspberry Pi down (sudo shutdown now) and unplug the power.
  2. Check the cable at BOTH ends: it must be a Raspberry Pi 5 camera cable,
     pushed all the way into CAM/DISP 0 or CAM/DISP 1, with the latches closed.
  3. Plug the power back in. The camera must be connected BEFORE the Pi is
     powered on: it is not detected if it is connected while the Pi is on.
  4. In a terminal, "rpicam-hello --list-cameras" must list the camera.
Then run this again."""


def take_photo(path=PHOTO, seconds=3):
    """Take the grayscale photo of the project with the Raspberry Pi camera.

    A preview window shows the camera for `seconds` seconds, then the photo is
    saved as a PGM file of PHOTO_SIZE pixels. Raises LabError, with what to
    check, if there is no camera.
    """
    import shutil
    import subprocess

    if not shutil.which("rpicam-still"):
        raise LabError("rpicam-still not found: the camera software is missing.\n"
                       "Install it with: sudo apt install -y rpicam-apps")
    width, height = PHOTO_SIZE
    raw = path + ".yuv"
    cmd = ["rpicam-still", "-t", str(seconds * 1000), "--encoding", "yuv420",
           "--width", str(width), "--height", str(height), "-o", raw]
    print(f"Look at the camera: taking the photo in {seconds} seconds...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and "no cameras" not in result.stderr.lower():
        # Probably no screen for the preview (e.g. over SSH): try without it.
        result = subprocess.run(cmd + ["-n"], capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(raw):
        if "no cameras" in result.stderr.lower():
            raise LabError(NO_CAMERA)
        last = (result.stderr.strip().splitlines() or ["unknown error"])[-1]
        raise LabError(f"The camera did not take the photo: {last}\n\n{NO_CAMERA}")

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


def photo_mode():
    """Console: take the photo, or explain what to check."""
    print(CLEAR + BOLD + "PHOTO" + RESET + "\n")
    try:
        take_photo()
    except LabError as err:
        print("\n" + RED + str(err) + RESET)
    ask(f"\n{DIM}[Enter] back to menu{RESET} ")


def require_photo(image):
    """The photo as rows, or LabError telling the student to take it."""
    try:
        return load_photo(image)
    except FileNotFoundError:
        raise LabError(NO_PHOTO.format(image)) from None


# ---------------------------------------------------------------------------
# 3. Race: Python against every C and assembly version, on the photo.
# ---------------------------------------------------------------------------
BAR_WIDTH = 30
SCALE_STEPS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def bar(fraction, width=BAR_WIDTH):
    filled = min(width, int(fraction * width))
    return "█" * filled + "░" * (width - filled)


def check_yours_output():
    """The output of conv_bench.py --check-yours, run in a separate process
    so that a student version that crashes or never ends cannot take the
    notebook down with it ("" if it does not finish)."""
    import subprocess

    try:
        return subprocess.run(["python3", "conv_bench.py", "--check-yours"], cwd=HERE,
                              capture_output=True, text=True, timeout=60).stdout
    except subprocess.TimeoutExpired:
        return ""


def yours_ok():
    """Names of the student versions that are correct."""
    ok = {line[3:] for line in check_yours_output().splitlines() if line.startswith("OK ")}
    for name in sorted(YOURS - ok):
        print(f"{name} is not in the race: it is not correct yet.", flush=True)
    return ok


def pin_to_core(core):
    """Run the calling thread only on this CPU core (Linux). Elsewhere, or if
    the core does not exist, the thread simply runs unpinned."""
    try:
        os.sched_setaffinity(0, {core})
    except (AttributeError, OSError):
        pass


def run_race(image, draw, interval=0.1):
    """Run the race and call draw(panel1, panel2, full_bar, elapsed) repeatedly.

    So that no version slows another one down:
      - Python runs on a CPU core of its own;
      - the C and assembly versions run one after another on another core,
        never at the same time, each on one copy of the photo.

    panel1: [(name, fraction, status)] progress of the photo for every version.
    panel2: [(name, fraction, count)] how many photos each C/assembly version
            could have processed in the time Python has used so far:
            Python's time / that version's time. It is computed from the
            measured times, not run. A full bar is full_bar photos.
    Returns the final state: times, counts and whether all outputs match.
    """
    correct_yours = yours_ok()
    natives = [(short_name(n), f) for n, f, _ in load_versions()
               if f is not None and (n not in YOURS or n in correct_yours)]
    img = require_photo(image)
    k = EDGE_KERNEL
    h, w = len(img), len(img[0])
    flat_img, flat_k = flatten(img, k)
    oh, ow = h - (KSIZE - 1), w - (KSIZE - 1)
    names = ["Python"] + [n for n, _ in natives]
    try:
        cores = sorted(os.sched_getaffinity(0))
    except AttributeError:
        cores = [0]
    python_core, native_core = cores[-1], cores[-2] if len(cores) > 1 else cores[-1]

    # finish: seconds each version needed for the photo (None = not done yet).
    state = {"rows": 0, "t0": 0.0, "python": None, "outputs": {},
             "finish": dict.fromkeys(names), "running": None}

    def python_worker():
        pin_to_core(python_core)
        out = [[0] * ow for _ in range(oh)]
        for y in range(oh):                    # same loops as conv_bench.py
            for x in range(ow):
                acc = 0
                for ky in range(KSIZE):
                    for kx in range(KSIZE):
                        acc += img[y + ky][x + kx] * k[ky][kx]
                out[y][x] = acc
            state["rows"] = y + 1
        state["finish"]["Python"] = time.perf_counter() - state["t0"]
        state["python"] = array("i", [v for row in out for v in row])

    def native_worker():
        pin_to_core(native_core)
        for name, func in natives:             # one at a time
            state["running"] = name
            out = array("i", [0]) * (oh * ow)
            c_img, c_out, c_k = as_c_array(flat_img), as_c_array(out), as_c_array(flat_k)
            t0 = time.perf_counter()
            func(c_img, c_out, c_k, h, w)
            state["finish"][name] = time.perf_counter() - t0
            state["outputs"][name] = out
        state["running"] = None

    def panels():
        finish = state["finish"]
        python_time = finish["Python"] or time.perf_counter() - state["t0"]
        panel1, counts = [], []
        for name in names:
            if name == "Python":
                frac = state["rows"] / oh
            else:
                frac = 1.0 if finish[name] is not None else 0.0
            if finish[name] is not None:
                status = f"done in {finish[name]:.3f} s"
            elif name == state["running"]:
                status = "running..."
            elif name == "Python":
                status = f"{frac * 100:5.1f}%"
            else:
                status = "waiting"
            panel1.append((name, frac, status))
            if name != "Python":
                counts.append((name, int(python_time / finish[name]) if finish[name] else 0))
        most = max((c for _, c in counts), default=0)
        per_char = next((s for s in SCALE_STEPS if most <= s * BAR_WIDTH), SCALE_STEPS[-1])
        full = per_char * BAR_WIDTH
        return panel1, [(n, c / full, c) for n, c in counts], full

    threads = [threading.Thread(target=python_worker, daemon=True),
               threading.Thread(target=native_worker, daemon=True)]
    # The C/assembly thread needs Python's lock for a moment after each
    # version; a short switch interval keeps it from waiting behind the
    # Python loop, so its measured times stay accurate.
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.0005)
    try:
        state["t0"] = time.perf_counter()
        for t in threads:
            t.start()
        while True:
            done = not any(t.is_alive() for t in threads)  # read before drawing:
            draw(*panels(), time.perf_counter() - state["t0"])  # last frame = 100 %
            if done:
                break
            time.sleep(interval)
    finally:
        sys.setswitchinterval(old_interval)
    state["ok"] = all(state["outputs"][n] == state["python"] for n, _ in natives)
    state["counts"] = {n: int(state["finish"]["Python"] / state["finish"][n])
                       for n, _ in natives}
    return state


RACE_INTRO = (
    "Python starts the photo on a CPU core of its own. On another core, the C\n"
    "and assembly versions process the same photo one after another, never at\n"
    "the same time, so no version slows another one down. Panel 2 shows how\n"
    "many photos each C and assembly version could process in the time Python\n"
    "has used so far (Python's time / that version's time).")
PANEL2_TITLE = "Photos each version could process in Python's time (each █ = {} photos)"
PANEL2_TITLE_HTML = "Photos each version could process in Python's time (full bar = {} photos)"


def race_summary(state):
    fin, count = state["finish"], state["counts"]
    best = max(count, key=count.get)
    return ([f"Python needed {fin['Python']:.2f} s for the photo. In that time:"]
            + [f"  {n:<7} ({fin[n]:.3f} s per photo) could process {c:5d} photos"
               for n, c in count.items()]
            + [f"Fastest: {best}.",
               "All versions produced the same output." if state["ok"]
               else "MISMATCH between versions!"])


def race_color(name):
    return YELLOW if name == "Python" else CYAN if name.startswith("C") else GREEN


def race_mode(image=PHOTO):
    """Console version of the race, drawn with ANSI escape codes."""
    print(CLEAR + BOLD + "RACE" + RESET + f"   preparing {image}...", flush=True)
    drawn = [0]                                    # lines drawn by the last frame

    def draw(panel1, panel2, full, elapsed):
        if not drawn[0]:
            print(CLEAR + BOLD + "RACE" + RESET + f"   {image}, edge-detection kernel\n")
            print(RACE_INTRO + "\n")
            sys.stdout.write(HIDE_CURSOR)
        lines = [BOLD + "1. One photo" + RESET]
        lines += [f"{race_color(n)}{n:<9}{RESET} {bar(f)} {s}" for n, f, s in panel1]
        lines += ["", BOLD + "2. " + PANEL2_TITLE.format(full // BAR_WIDTH) + RESET]
        lines += [f"{race_color(n)}{n:<9}{RESET} {bar(f)} {c:5d}" for n, f, c in panel2]
        lines += [f"{DIM}time: {elapsed:5.1f} s{RESET}"]
        up = f"\033[{drawn[0]}F" if drawn[0] else ""
        sys.stdout.write(up + "".join(l + "\033[K\n" for l in lines))
        sys.stdout.flush()
        drawn[0] = len(lines)

    try:
        state = run_race(image, draw)
    except LabError as err:
        print("\n" + RED + str(err) + RESET)
        ask(f"\n{DIM}[Enter] back to menu{RESET} ")
        return
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
# Parts 3, 4 and 7 of the notebook: the code students write.
# ---------------------------------------------------------------------------
YOUR_START = "// ---- YOUR CODE STARTS HERE ----"
YOUR_END = "// ---- YOUR CODE ENDS HERE ----"


def build_yours(code, filename, indent=""):
    """Put `code` between the YOUR CODE markers of src/<filename>, build it
    with make and run the benchmark without Python. Compiler and assembler
    errors point to the line of `code`, not of the file."""
    import re
    import subprocess

    rel = os.path.join("src", filename)
    path = os.path.join(HERE, rel)
    with open(path) as f:
        text = f.read()
    if YOUR_START not in text or YOUR_END not in text:
        raise LabError(f"{rel} lost its YOUR CODE markers. Restore it with:\n"
                       f"  git checkout {rel}")
    head, rest = text.split(YOUR_START, 1)
    tail = rest.split(YOUR_END, 1)[1]
    lines = code.strip("\n").split("\n")
    first = (head + YOUR_START).count("\n") + 2  # file line of the first code line
    with open(path, "w") as f:
        f.write(head + YOUR_START + "\n" + "\n".join(lines) + "\n" + indent + YOUR_END + tail)

    print("Building...", flush=True)
    make = subprocess.run(["make"], cwd=HERE, capture_output=True, text=True)
    if make.returncode != 0:
        problems = []
        pattern = re.escape(filename) + r":(\d+):(?:\d+:)? (?:Error|error): (.*)"
        for match in re.finditer(pattern, make.stderr):
            n = int(match.group(1)) - first
            where = (f"line {n + 1} of your code: {lines[n].strip()}"
                     if 0 <= n < len(lines) else f"{rel}, line {match.group(1)}")
            problems.append(f"  {where}\n    -> {match.group(2)}")
        # Only the first two: the next ones are usually caused by the first.
        raise LabError("The compiler found an error, so your version was NOT BUILT:\n"
                       + ("\n".join(problems[:2]) or make.stderr.strip()))
    print("Built.", flush=True)
    return lines


def run_yours_benchmark(name):
    """Time only version `name`, in its own process: if the student's
    code crashes or never ends, the notebook survives and says why. Then a
    check of version `name` with random images and kernels: the edge kernel
    of the photo is symmetric, so it cannot catch a transposed kernel."""
    import subprocess

    try:
        # Same command as the other benchmark cells of the notebook.
        bench = subprocess.run(["python3", "conv_bench.py", "--only", short_name(name)],
                               cwd=HERE, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise LabError("The benchmark did not finish in 2 minutes: your code probably "
                       "never ends.\nCheck the loop conditions and that every loop "
                       "variable is increased.") from None
    print(bench.stdout + bench.stderr)
    if bench.returncode < 0:
        raise LabError("Your code crashed the program (it read or wrote outside the "
                       "image).\nCheck the loop limits and the indexes.")
    if f"OK {name}" in check_yours_output():
        print(f"Extra check with random images and kernels: {name} is OK.")
    else:
        raise LabError(f"Extra check with random images and kernels: {name} gives a "
                       "WRONG result.\nThe photo's edge kernel is symmetric, so some "
                       "mistakes only show up with other kernels:\ncheck the kernel "
                       "index k[ky * 3 + kx] (ky and kx not swapped) and the loop limits.")


def build_c_v2(code):
    """Part 3: build the student's C v2 (row order) and measure it."""
    build_yours(code, "conv_student_c.c")
    print()
    run_yours_benchmark("C v2 rows (yours)")


def build_v1(code):
    """Part 5: build the student's half of assembly v1 and measure it."""
    build_yours(code, "conv_student_v1.S", indent="        ")
    print()
    run_yours_benchmark("ASM v1 brute (yours)")


def build_v3(code):
    """Part 7: build the student's assembly v3 (one output pixel) and measure it."""
    import re

    lines = build_yours(code, "conv_student.S", indent="        ")
    count = sum(1 for line in lines if re.match(r"\s*madd\b", line))
    print(f"Your code has {count} madd instructions (8 when you are done).\n", flush=True)
    run_yours_benchmark("ASM v3 MAC (yours)")


# ---------------------------------------------------------------------------
# Jupyter notebook versions (project.ipynb). IPython is imported only here, so
# the console demo keeps working with the standard library alone.
# ---------------------------------------------------------------------------
def html_color(name):
    return "#b58900" if name == "Python" else "#268bd2" if name.startswith("C") else "#2aa198"


def notebook_race(image=PHOTO):
    """The race inside a notebook cell, redrawn in place as HTML."""
    from html import escape
    from IPython.display import HTML, display

    print(RACE_INTRO)
    print(f"\nPreparing {image}...", flush=True)
    handle = display(HTML(""), display_id=True)

    def row(name, frac, text):
        color = html_color(name)
        return (f'<tr><td style="color:{color};font-weight:bold;padding:2px 12px 2px 0;'
                f'text-align:left">{name}</td>'
                f'<td style="width:300px;padding:2px 0"><div style="background:#ddd;'
                f'height:14px"><div style="background:{color};height:14px;'
                f'width:{min(frac, 1) * 100:.1f}%"></div></div></td>'
                f'<td style="padding:2px 12px;font-family:monospace">{escape(text)}</td></tr>')

    def draw(panel1, panel2, full, elapsed):
        html = ["<b>1. One photo</b><table style='border-collapse:collapse'>"]
        html += [row(n, f, s) for n, f, s in panel1]
        html += ["</table><br><b>2. " + escape(PANEL2_TITLE_HTML.format(full)) + "</b>"
                 "<table style='border-collapse:collapse'>"]
        html += [row(n, f, f"{c} photos") for n, f, c in panel2]
        html += [f"</table><p style='font-family:monospace'>time: {elapsed:5.1f} s</p>"]
        handle.update(HTML("".join(html)))

    state = run_race(image, draw)
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


def notebook_image(image=PHOTO, zoom=8, width=480):
    """Show the photo, a zoom on its centre, the edge kernel and the edges.

    The convolution runs on the whole photo with the C version (it takes a
    fraction of a second); both images are then shrunk to `width` pixels to
    fit on the screen.
    """
    from IPython.display import HTML, display

    img = require_photo(image)
    h, w = len(img), len(img[0])
    flat_img, flat_k = flatten(img, EDGE_KERNEL)
    out, t = run_native(load("libconv_c.so", "conv_c_cols"), flat_img, flat_k, h, w)
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
    display(HTML(
        f"<p>Your photo: <b>{w} × {h} = {w * h:,} pixels</b>, each a number from 0 "
        f"(black) to 255 (white), {w * h * 4 / 1e6:.0f} MB as 32-bit integers. The "
        f"edge-detection kernel gives 0 where the brightness does not change, and a large "
        f"value at edges. C v1 computed all {oh * ow:,} output pixels "
        f"in {t * 1e3:.0f} ms.</p>"
        + html_picture(small_in, "Input photo", scale=1)
        + html_picture(edges, "Output: edges (dark = strong edge)", scale=1)
        + "<br>"
        + html_numbers(centre, f"Zoom: {zoom} × {zoom} pixels at the centre")
        + html_numbers(EDGE_KERNEL, "Edge-detection kernel", gray=False)))


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


def notebook_animation(seed=4082, step_seconds=1.0, cell=32):
    """Animate the kernel sliding over the 6 x 8 example of notebook_step.

    Pure HTML and CSS (no JavaScript), so it also moves in the exported HTML.
    Each output pixel gets one time slot: the window moves there, its
    calculation shows, and the output pixel appears. The mouse pauses it.
    """
    from IPython.display import HTML, display

    img, k, out = step_example(seed)
    oh, ow = len(out), len(out[0])
    n = oh * ow
    total = n * step_seconds
    css = [f".cva{{position:relative;font-family:monospace;color:#000;background:#fff;"
           f"padding:12px;display:inline-block;line-height:normal}}"
           f".cva:hover *{{animation-play-state:paused}}"
           f".cva-grid{{position:relative;display:grid;grid-template-columns:repeat(var(--c),{cell}px);"
           f"grid-auto-rows:{cell}px;margin:4px 32px 12px 0}}"
           f".cva-grid div{{box-sizing:border-box;border:1px solid #ccc;text-align:center;"
           f"line-height:{cell - 2}px}}"
           f".cva-grid .cva-box{{position:absolute;box-sizing:border-box;border:3px solid #f57f17;"
           f"background:rgba(255,213,79,.45);animation:cva-move {total}s step-end infinite}}"
           f".cva-grid .cva-out{{position:absolute;box-sizing:border-box;width:{cell}px;height:{cell}px;"
           f"border:3px solid #f57f17;animation:cva-move-out {total}s step-end infinite}}"
           f".cva-calc{{position:relative;height:3em}}"
           f".cva-calc p{{position:absolute;margin:0;opacity:0}}"
           f".cva span{{display:inline-block}}"]

    def moves(name):
        frames = [f"{100 * i / n:.4f}%{{left:{(i % ow) * cell}px;top:{(i // ow) * cell}px}}"
                  for i in range(n)]
        return f"@keyframes {name}{{" + "".join(frames) + "}"

    css.append(moves("cva-move"))
    css.append(moves("cva-move-out"))
    calcs, outs = [], []
    for i in range(n):
        y, x = divmod(i, ow)
        start = f"{i * step_seconds:g}s"
        # Calculation i: visible during its own slot only.
        css.append(f"@keyframes cva-c{i}{{0%{{opacity:1}}{100 / n:.4f}%{{opacity:0}}}}")
        terms = " + ".join(f"{img[y + ky][x + kx]}·" + (f"({c})" if (c := k[ky][kx]) < 0 else f"{c}")
                           for ky in range(KSIZE) for kx in range(KSIZE))
        calcs.append(f'<p style="animation:cva-c{i} {total}s step-end {start} infinite">'
                     f"out[{y}][{x}] = {terms}<br>= <b>{out[y][x]}</b></p>")
        # Output pixel i: appears in its slot and stays until the loop restarts.
        css.append(f"@keyframes cva-o{i}{{0%{{opacity:1}}{100 * (n - i) / n:.4f}%{{opacity:0}}}}")
        outs.append(f'<div><span style="opacity:0;animation:cva-o{i} {total}s step-end '
                    f'{start} infinite">{out[y][x]}</span></div>')

    def grid(cols, cells, extra=""):
        return (f'<div class="cva-grid" style="--c:{cols}">' + "".join(cells) + extra + "</div>")

    box = f'<div class="cva-box" style="width:{3 * cell}px;height:{3 * cell}px"></div>'
    display(HTML(
        "<style>" + "".join(css) + "</style><div class='cva'>"
        "<div style='display:flex;flex-wrap:wrap;align-items:flex-start'>"
        "<div><b>Input image</b> (6 × 8)" + grid(8, [f"<div>{v}</div>" for r in img for v in r], box)
        + "</div><div><b>Kernel</b>" + grid(3, [f"<div>{v}</div>" for r in k for v in r])
        + "</div><div><b>Output image</b> (4 × 6)" + grid(ow, outs, '<div class="cva-out"></div>')
        + "</div></div><div class='cva-calc'>" + "".join(calcs) + "</div>"
        f"<small>One output pixel every {step_seconds:g} s, then it starts again. "
        "Put the mouse on the animation to pause it.</small></div>"))


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
    p.add_argument("mode", nargs="?", choices=["step", "photo", "race"],
                   help="go straight to one mode instead of the menu")
    p.add_argument("--image", metavar="FILE.pgm", default=PHOTO,
                   help=f"photo for the race (default {PHOTO})")
    args = p.parse_args()

    if platform.machine() != "aarch64":
        sys.exit(f"error: this project needs a 64-bit ARM system (aarch64), "
                 f"this one is {platform.machine()}. Check 'uname -m'.")
    try:
        load("libconv_c.so", "conv_c_cols")
    except RuntimeError as err:
        sys.exit(f"error: {err}")
    modes = {"1": "step", "2": "photo", "3": "race"}

    choice = args.mode
    while True:
        if not args.mode:
            print(CLEAR + BOLD + "2D CONVOLUTION: Python -> C -> Assembly" + RESET + "\n")
            print("  1) Step by step   how a convolution works")
            print("  2) Photo          take the photo with the camera")
            print("  3) Race           how fast each language processes the photo")
            print("  q) Quit")
            key = ask("\n> ")
            if key == "q":
                break
            choice = modes.get(key)
        if choice == "step":
            step_mode()
        elif choice == "photo":
            photo_mode()
        elif choice == "race":
            race_mode(args.image)
        if args.mode:
            break
    print(SHOW_CURSOR, end="")


if __name__ == "__main__":
    main()
