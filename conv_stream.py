#!/usr/bin/env python3
"""
conv_stream.py - live video: the camera and its convolution, side by side.

The camera streams at the size of the project photo (2592 x 1944). Every
frame goes through the version you choose (Python, C or assembly) at full
size, and a page shows the camera and the edges side by side, with the time
each version needs per frame. Only the fast versions keep up with the camera.

At this size the camera gives at most 15 frames per second, so every version
faster than that looks the same. So the video is always in slow motion: each
frame is convolved 7 times (Python: once), every frame rate is divided by 7
and the differences between the versions show up in the video. The table of
the page keeps the real time and frames per second of each version.

    stream = notebook_stream()     # in project.ipynb
    stream.stop()                  # stops the video and frees the camera

    python3 conv_stream.py         # from a terminal: open the address it prints

The page is served by this program on this Raspberry Pi only (127.0.0.1).
While the video runs, no other program can use the camera.

Build the libraries first with "make". Only the Python standard library is
used.
"""
import argparse
import atexit
import ctypes
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
from array import array
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from conv_bench import BUILD, EDGE_KERNEL, KSIZE, PHOTO_SIZE, YOURS, as_c_array, conv_python

U8_PTR = ctypes.POINTER(ctypes.c_uint8)
I32_PTR = ctypes.POINTER(ctypes.c_int32)
LONG = ctypes.c_long
PYTHON = "Python"
DEFAULT_VERSION = "ASM v4 NEON"
# Convolutions per camera frame. One takes 9.5 ms with ASM v4 and the camera
# sends a frame every 67 ms, so with 7 the fastest version just keeps up.
WORK = 7
V3_NAME = "ASM v3 MAC (yours)"
V3_SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "conv_student_v3.S")


def load_helpers():
    """The conversions of src/stream.c (y_to_i32, gray_small, edges_small)."""
    path = os.path.join(BUILD, "libconv_stream.so")
    if not os.path.exists(path):
        raise RuntimeError(f"{path} not found. Run 'make' and fix any error it shows.")
    lib = ctypes.CDLL(path)
    lib.y_to_i32.argtypes = [U8_PTR, LONG, LONG, LONG, I32_PTR]
    lib.y_to_i32.restype = None
    lib.gray_small.argtypes = [U8_PTR, LONG, LONG, LONG, LONG, U8_PTR]
    lib.gray_small.restype = None
    lib.edges_small.argtypes = [I32_PTR, LONG, LONG, LONG, LONG, I32_PTR, U8_PTR]
    lib.edges_small.restype = LONG
    return lib


def v3_finished():
    """ASM v3 starts as a working copy of ASM v2, so its result is correct before
    the student writes anything. It is finished when it has its 8 madd lines."""
    with open(V3_SOURCE) as f:
        return sum(1 for line in f if re.match(r"\s*madd\b", line)) >= 8


def load_stream_versions():
    """[(name, function)] of the versions to show: Python, then every C and
    assembly version that is built (the ones students write, only if ready)."""
    from conv_bench import load_versions
    from conv_demo import check_yours_output

    ready = {line[3:] for line in check_yours_output().splitlines() if line.startswith("OK ")}
    if not v3_finished():
        ready.discard(V3_NAME)
    for name in sorted(YOURS - ready):
        print(f"{name} is not in the video: its code is not ready yet.", flush=True)
    return [(PYTHON, None)] + [(n, f) for n, f, _ in load_versions()
                               if f is not None and (n not in YOURS or n in ready)]


def detect_stride(data, w, h):
    """Length in bytes of one camera row (the camera can pad its rows).

    Each frame is a YUV420 image: the Y plane (h rows of `stride` bytes)
    and two colour planes, stride * h * 3 / 2 bytes in all. With the right
    stride, consecutive rows of the first frame look alike; with a wrong one
    they are shifted, so the candidate with the smallest difference wins.
    """
    candidates = []
    for align in (64, 32, 128, 16, 1):
        stride = -(-w // align) * align
        if stride not in candidates and stride * h * 3 // 2 <= len(data):
            candidates.append(stride)
    best = None
    for stride in candidates:
        diff = 0
        for r in range(h // 4, h // 4 + 48):
            a = data[r * stride:r * stride + w:4]
            b = data[(r + 1) * stride:(r + 1) * stride + w:4]
            diff += sum(abs(x - y) for x, y in zip(a, b))
        if best is None or diff < best[0]:
            best = (diff, stride)
    return best[1]


class Frame:
    """A byte buffer with its ctypes view, made once and reused."""

    def __init__(self, size):
        self.data = bytearray(size)
        self.c = (ctypes.c_uint8 * size).from_buffer(self.data)


class Rate:
    """Frames per second over the last frames."""

    def __init__(self, n=15):
        self.times = deque(maxlen=n)

    def tick(self):
        self.times.append(time.perf_counter())

    def reset(self):
        self.times.clear()

    def fps(self):
        if len(self.times) < 2:
            return None
        return (len(self.times) - 1) / (self.times[-1] - self.times[0])


class Stream:
    """Camera -> convolution -> page. start() returns self, stop() frees all.

    Three threads:
      - reader: reads the camera frames from rpicam-vid and shrinks each one
        for the screen, so the camera image stays live whatever the version;
      - worker: on a CPU core of its own, takes the newest frame, runs the
        chosen version on it at full size WORK times in a row and times
        only those calls;
      - server: the page and the frames, on http://127.0.0.1:<port>/.
    """

    def __init__(self, width=PHOTO_SIZE[0], height=PHOTO_SIZE[1], framerate=15, shrink=3,
                 stride=None, port=0, versions=None, helpers=None, command=None):
        self.w, self.h, self.framerate, self.f = width, height, framerate, shrink
        self.oh, self.ow = height - (KSIZE - 1), width - (KSIZE - 1)
        self.stride = stride
        self.port = port
        self.versions = versions               # for tests: [(name, function)]
        self.lib = helpers                     # for tests: object with the 3 helpers
        self.command = command                 # for tests: a fake camera
        self.selected = DEFAULT_VERSION
        self.ms = {}                           # name -> ms of its last frame
        self.busy = None                       # version running right now
        self.shown = None                      # version of the edges on the page
        self.error = None
        self.proc = self.server = None
        self.cond = threading.Condition()
        self.stopping = threading.Event()
        self.cam_id = self.res_id = 0
        self.cam_rate, self.res_rate = Rate(), Rate()
        self.top = 0.0                         # smoothed 99th percentile of the edges
        self.url = None

    # ---- start and stop ----------------------------------------------------
    def start(self):
        if self.lib is None:
            self.lib = load_helpers()
        if self.versions is None:
            self.versions = load_stream_versions()
        self.funcs = dict(self.versions)
        if self.selected not in self.funcs:
            self.selected = self.versions[-1][0]
        self._start_camera()
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()
        self._start_server()
        atexit.register(self.stop)
        return self

    def stop(self):
        """Stop the video, free the camera and close the page's server."""
        self.stopping.set()
        with self.cond:
            self.cond.notify_all()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.server is not None:
            server, self.server = self.server, None
            server.shutdown()
            server.server_close()
            print("Video stopped: the camera is free.", flush=True)

    def _start_camera(self):
        if self.command is None:
            if not shutil.which("rpicam-vid"):
                raise RuntimeError("rpicam-vid not found: the camera software is missing.\n"
                                   "Install it with: sudo apt install -y rpicam-apps")
            self.command = ["rpicam-vid", "-t", "0", "-n", "--codec", "yuv420",
                            "--width", str(self.w), "--height", str(self.h),
                            "--framerate", str(self.framerate), "-o", "-"]
        self.log = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=self.log,
                                     bufsize=0)
        try:                                   # bigger pipe: fewer reads per frame
            import fcntl
            fcntl.fcntl(self.proc.stdout, 1031, 1 << 20)   # F_SETPIPE_SZ
        except (ImportError, OSError):
            pass

        # Two frames of the largest possible size, to find the row length.
        largest = (-(-self.w // 128) * 128) * self.h * 3 // 2
        data = self._read_exactly(2 * largest)
        if data is None:
            self.stop()
            self.log.seek(0)
            lines = self.log.read().decode(errors="replace").strip().splitlines()
            from conv_demo import NO_CAMERA
            if any("no cameras" in line.lower() for line in lines):
                raise RuntimeError(NO_CAMERA)
            raise RuntimeError("The camera did not start the video: "
                               + (lines[-1] if lines else "unknown error")
                               + "\nIs another program (or another video cell) using it?")
        if self.stride is None:
            self.stride = detect_stride(data, self.w, self.h)
        self.size = self.stride * self.h * 3 // 2
        self.pending = data[len(data) // self.size * self.size:]   # start of the next frame

    def _read_exactly(self, n):
        chunks, got = [], 0
        while got < n:
            chunk = self.proc.stdout.read(n - got)
            if not chunk:
                return None
            chunks.append(chunk)
            got += len(chunk)
        return b"".join(chunks)

    # ---- threads -------------------------------------------------------------
    def _reader(self):
        """Read every camera frame; publish it and its small copy for the screen."""
        sw, sh = self.w // self.f, self.h // self.f
        reading, self.frame = Frame(self.size), Frame(self.size)
        small, self.cam_small = Frame(sw * sh), Frame(sw * sh)
        pending = self.pending
        while not self.stopping.is_set():
            view = memoryview(reading.data)
            n = len(pending)
            view[:n] = pending
            pending = b""
            while n < self.size:
                got = self.proc.stdout.readinto(view[n:])
                if not got:
                    if not self.stopping.is_set():
                        self.error = "The camera stopped sending frames."
                        self.stopping.set()
                    with self.cond:
                        self.cond.notify_all()
                    return
                n += got
            view.release()
            self.lib.gray_small(reading.c, self.stride, self.h, self.w, self.f, small.c)
            with self.cond:
                reading, self.frame = self.frame, reading       # the worker gets the newest
                small, self.cam_small = self.cam_small, small
                self.cam_id += 1
                self.cam_rate.tick()
                self.cond.notify_all()

    def _worker(self):
        """Run the chosen version on the newest frame, again and again."""
        from conv_demo import pin_to_core

        try:
            pin_to_core(sorted(os.sched_getaffinity(0))[-1])
        except AttributeError:
            pass
        w, h, oh, ow, f = self.w, self.h, self.oh, self.ow, self.f
        img, out = array("i", [0]) * (w * h), array("i", [0]) * (oh * ow)
        c_img, c_out = as_c_array(img), as_c_array(out)
        k = array("i", [c for row in EDGE_KERNEL for c in row])
        c_k = as_c_array(k)
        tmp = array("i", [0]) * ((oh // f) * (ow // f))
        c_tmp = as_c_array(tmp)
        small, self.res_small = Frame((oh // f) * (ow // f)), Frame((oh // f) * (ow // f))
        last = 0
        while True:
            with self.cond:
                self.cond.wait_for(lambda: self.cam_id != last or self.stopping.is_set())
                if self.stopping.is_set():
                    return
                last = self.cam_id
                self.lib.y_to_i32(self.frame.c, self.stride, h, w, c_img)
                name = self.busy = self.selected
            if name == PYTHON:
                rows = [img[r * w:(r + 1) * w].tolist() for r in range(h)]
                t0 = time.perf_counter()
                result = conv_python(rows, EDGE_KERNEL)
                seconds = time.perf_counter() - t0
                for r, row in enumerate(result):
                    out[r * ow:(r + 1) * ow] = array("i", row)
            else:
                # The same frame WORK times: only the convolution is repeated,
                # the conversions before and after it run once per frame.
                done = 0
                t0 = time.perf_counter()
                while done < WORK and not self.stopping.is_set():
                    self.funcs[name](c_img, c_out, c_k, h, w)
                    done += 1
                seconds = (time.perf_counter() - t0) / max(done, 1)
            p = self.lib.edges_small(c_out, oh, ow, f, int(self.top), c_tmp, small.c)
            self.top = p if self.top == 0 else 0.8 * self.top + 0.2 * p
            with self.cond:
                small, self.res_small = self.res_small, small
                self.ms[name] = seconds * 1e3  # time of ONE convolution
                if name != self.shown:         # frames/s of this version only
                    self.res_rate.reset()
                self.shown = name
                self.busy = None
                self.res_id += 1
                self.res_rate.tick()
                self.cond.notify_all()

    # ---- page ----------------------------------------------------------------
    def state(self):
        """What the page shows besides the two images (call with cond held)."""
        cam_fps = self.cam_rate.fps()
        return {
            "running": not self.stopping.is_set(), "error": self.error,
            "width": self.w, "height": self.h, "stride": self.stride,
            "macs": self.oh * self.ow * KSIZE * KSIZE,
            "selected": self.selected, "busy": self.busy, "shown": self.shown,
            "work": WORK,
            "camera_fps": cam_fps, "result_fps": self.res_rate.fps(),
            "versions": [{"name": n, "ms": self.ms.get(n)} for n, _ in self.versions],
        }

    def frames(self, cam_seen, res_seen):
        """Wait (up to 2 s) for a frame the page has not drawn yet and return
        the reply: 4-byte length, JSON, then the new images, if any."""
        with self.cond:
            self.cond.wait_for(lambda: self.cam_id != cam_seen or self.res_id != res_seen
                               or self.stopping.is_set(), timeout=2)
            head = {"state": self.state(), "cam": None, "res": None}
            images = []
            if self.cam_id != cam_seen and self.cam_id > 0:
                head["cam"] = {"id": self.cam_id, "w": self.w // self.f, "h": self.h // self.f}
                images.append(bytes(self.cam_small.data))
            if self.res_id != res_seen and self.res_id > 0:
                head["res"] = {"id": self.res_id, "w": self.ow // self.f, "h": self.oh // self.f}
                images.append(bytes(self.res_small.data))
        text = json.dumps(head).encode()
        return struct.pack("<I", len(text)) + text + b"".join(images)

    def select(self, name):
        if name in self.funcs:
            with self.cond:
                self.selected = name

    def _start_server(self):
        stream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):      # keep the notebook output clean
                pass

            def reply(self, body, kind):
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                url = urlparse(self.path)
                query = parse_qs(url.query)
                if url.path == "/":
                    self.reply(PAGE.encode(), "text/html; charset=utf-8")
                elif url.path == "/frames":
                    seen = [int(query.get(key, ["0"])[0]) for key in ("cam", "res")]
                    self.reply(stream.frames(*seen), "application/octet-stream")
                else:
                    self.send_error(404)

            def do_POST(self):
                url = urlparse(self.path)
                query = parse_qs(url.query)
                if url.path == "/select":
                    stream.select(query.get("v", [""])[0])
                elif url.path == "/stop":
                    threading.Thread(target=stream.stop, daemon=True).start()
                self.reply(b"ok", "text/plain")

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


# The page: two canvases, the buttons of the versions and their times. It asks
# for frames in a loop; each reply has only the images it has not drawn yet.
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Live convolution</title>
<style>
  body { margin: 0; padding: 10px; font: 14px system-ui, sans-serif; background: #fff; color: #111; }
  .views { display: flex; gap: 10px; }
  .view { flex: 1; min-width: 0; }
  .view b { display: block; margin-bottom: 4px; }
  canvas { width: 100%; height: auto; background: #ddd; display: block; border: 1px solid #bbb; }
  .bar { margin: 10px 0 6px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  button { font: inherit; padding: 4px 10px; border: 1px solid #888; border-radius: 4px;
           background: #f4f4f4; cursor: pointer; }
  button.on { background: #1a7f37; color: #fff; border-color: #1a7f37; }
  #stop { margin-left: auto; background: #b42318; color: #fff; border-color: #b42318; }
  table { border-collapse: collapse; margin-top: 6px; }
  td, th { padding: 2px 10px; text-align: right; border-bottom: 1px solid #ddd; }
  td:first-child, th:first-child { text-align: left; }
  tr.on td { font-weight: bold; }
  .ok { color: #1a7f37; } .slow { color: #b42318; }
  #status { margin-top: 6px; color: #444; }
</style></head><body>
<div class="views">
  <div class="view"><b id="camtitle">Camera</b><canvas id="cam"></canvas></div>
  <div class="view"><b id="restitle">Edges</b><canvas id="res"></canvas></div>
</div>
<div class="bar" id="buttons"></div>
<table><thead id="head"></thead><tbody id="rows"></tbody></table>
<div id="status">Starting...</div>
<script>
const $ = id => document.getElementById(id);
const pictures = {};
let cam = 0, res = 0, built = false;

function draw(canvas, px, w, h) {
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w; canvas.height = h;
    pictures[canvas.id] = canvas.getContext("2d").createImageData(w, h);
  }
  const picture = pictures[canvas.id];
  const rgba = new Uint32Array(picture.data.buffer);
  for (let i = 0; i < px.length; i++) rgba[i] = 0xff000000 | px[i] * 0x010101;
  canvas.getContext("2d").putImageData(picture, 0, 0);
}

function fmt(v, digits) { return v == null ? "-" : v.toFixed(digits); }

function build(s) {
  for (const v of s.versions) {
    const b = document.createElement("button");
    b.textContent = v.name; b.dataset.name = v.name;
    b.onclick = () => fetch("select?v=" + encodeURIComponent(v.name), {method: "POST"});
    $("buttons").appendChild(b);
  }
  const stop = document.createElement("button");
  stop.id = "stop"; stop.textContent = "Stop video";
  stop.onclick = () => fetch("stop", {method: "POST"});
  $("buttons").appendChild(stop);
  $("head").innerHTML = "<tr><th>Version</th><th>Time per convolution</th>" +
    "<th>Max. frames/s (real)</th><th>Keeps up with the camera? (real)</th>" +
    "<th>Max. frames/s in this video</th></tr>";
  built = true;
}

function fps(v, digits) { return fmt(v, v != null && v < 1 ? 2 : digits); }

function update(s) {
  if (!built) build(s);
  for (const b of $("buttons").children)
    if (b.dataset.name) b.classList.toggle("on", b.dataset.name === s.selected);
  const camFps = s.camera_fps;
  $("camtitle").textContent = `Camera: ${s.width} × ${s.height} pixels, ${fmt(camFps, 1)} frames/s`;
  $("restitle").textContent = `Edges with ${s.shown || s.selected}: ` +
                              `${fmt(s.result_fps, 1)} frames/s in this video`;
  $("rows").innerHTML = s.versions.map(v => {
    const max = v.ms ? 1000 / v.ms : null;
    const video = max == null ? null : v.name === "Python" ? max : max / s.work;
    const keeps = max == null || camFps == null ? "-" : max >= camFps * 0.95
      ? '<span class="ok">yes</span>' : '<span class="slow">no</span>';
    return `<tr class="${v.name === s.selected ? "on" : ""}"><td>${v.name}</td>` +
           `<td>${v.ms == null ? "-" : v.ms >= 1000 ? fmt(v.ms / 1000, 1) + " s" : fmt(v.ms, 1) + " ms"}</td>` +
           `<td>${fps(max, 1)}</td><td>${keeps}</td><td>${fps(video, 1)}</td></tr>`;
  }).join("");
  let text = `Every frame: ${(s.width * s.height / 1e6).toFixed(1)} M pixels, ` +
             `${(s.macs / 1e6).toFixed(1)} M multiply-adds. Camera row: ${s.stride} bytes.`;
  if (s.busy === "Python") text += " Python is computing a frame (about 10 s each)...";
  if (!s.running) text = s.error || "Video stopped: the camera is free.";
  $("status").textContent = text;
}

async function loop() {
  while (true) {
    let buf;
    try {
      buf = await (await fetch(`frames?cam=${cam}&res=${res}`, {cache: "no-store"})).arrayBuffer();
    } catch (e) {
      $("status").textContent = "Video stopped: the camera is free.";
      return;
    }
    const n = new DataView(buf).getUint32(0, true);
    const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)));
    let at = 4 + n;
    for (const [key, canvas] of [["cam", $("cam")], ["res", $("res")]]) {
      const img = head[key];
      if (!img) continue;
      draw(canvas, new Uint8Array(buf, at, img.w * img.h), img.w, img.h);
      at += img.w * img.h;
      if (key === "cam") cam = img.id; else res = img.id;
    }
    update(head.state);
    if (!head.state.running) return;
  }
}
loop();
</script></body></html>
"""

_current = None


def notebook_stream(**options):
    """Start the live video and show it in the notebook. Returns the Stream:
    call its stop() to free the camera. Options: see Stream."""
    from IPython.display import HTML, IFrame, display
    from conv_demo import LabError

    global _current
    if _current is not None:
        _current.stop()
    try:
        _current = Stream(**options).start()
    except RuntimeError as err:
        raise LabError(str(err)) from None
    display(HTML(f'<p>The video runs until you click <b>Stop video</b> or run '
                 f'<code>stream.stop()</code>. Also on its own tab: '
                 f'<a href="{_current.url}" target="_blank">{_current.url}</a></p>'))
    display(IFrame(_current.url, width="100%", height=800))
    return _current


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8000, help="port of the page (default 8000)")
    p.add_argument("--framerate", type=int, default=15, help="camera frames per second")
    p.add_argument("--stride", type=int, help="camera row length in bytes (default: detected)")
    args = p.parse_args()
    try:
        stream = Stream(port=args.port, framerate=args.framerate, stride=args.stride).start()
    except RuntimeError as err:
        sys.exit(f"error: {err}")
    print(f"Open {stream.url} in the browser. Ctrl+C stops the video.")
    try:
        while not stream.stopping.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    stream.stop()


if __name__ == "__main__":
    main()
