# Live video test: the convolution on the camera

This branch (`streaming-test`) is an experiment. It adds a **live video** to the
project: on the left, the Raspberry Pi camera; on the right, the edges computed
from every frame by the version you choose (Python, C or assembly). The frames
are the size of the project photo, **2592 × 1944 pixels**, so every frame is the
same work as the photo: **45.3 million multiply-adds**.

The course guide (preparing the Pi, the notebook, handing in) is the README of
the [`main` branch](https://github.com/eTechLab-UPRM/Assembly-with-Raspberry-PI-5/blob/main/README.md).
This one explains only the live video.

- [Run it](#run-it)
- [What you see](#what-you-see)
- [How it works](#how-it-works)
- [Why the video stops at 15 frames per second](#why-the-video-stops-at-15-frames-per-second)
- [The slow motion: 7 convolutions per frame](#the-slow-motion-7-convolutions-per-frame)
- [Threads, cores and the GIL](#threads-cores-and-the-gil)
- [Options](#options)
- [Files of this branch](#files-of-this-branch)
- [Troubleshooting](#troubleshooting)

## Run it

The Pi must be ready as in Part A of the main guide (camera, tools, project and
Jupyter). Then, in a terminal:

```bash
cd ~/Assembly-with-Raspberry-PI-5
git fetch origin
git checkout streaming-test
make
~/jupyter-env/bin/jupyter notebook project.ipynb
```

In the notebook, run the first cells, your cells of Parts 3, 5 and 7 (C v2,
ASM v1 and ASM v3), and then **Part 10b. Live video**. Click **Stop
video**, or run `stream.stop()`, to free the camera.

Without the notebook, from a terminal:

```bash
python3 conv_stream.py
```

and open the address it prints in the browser. **Ctrl + C** stops it.

To go back to the course version: `git checkout main`.

## What you see

| Part of the page | What it shows |
|---|---|
| **Camera** (left) | The camera, live, with its frames per second |
| **Edges** (right) | The output of the chosen version, with its frames per second |
| **Version buttons** | The version that processes the frames; the change takes effect on the next frame |
| **Table** | For every version you have tried: the time of one convolution, the real frames per second it could process, whether that keeps up with the camera, and the frames per second it can reach in this video |
| **Stop video** | Stops the camera, the threads and the page |

The versions you write (C v2, ASM v1, ASM v3) appear only when they are finished
and give the correct result. ASM v3 starts as a working copy of ASM v2, so it also
needs its 8 `madd` instructions. If one is missing, the cell prints, for example,
`ASM v1 brute (yours) is not in the video: its code is not ready yet.`

## How it works

```
camera ──► reader ──► worker ──► web server ──► page in the notebook
(rpicam-vid) (thread 1)  (thread 2:     (thread 3)     (two images + table)
                          the convolution)
```

### 1. The camera: `rpicam-vid`

The program starts the camera with:

```
rpicam-vid -t 0 -n --codec yuv420 --width 2592 --height 1944 --framerate 15 -o -
```

- `-t 0`: no time limit. `-n`: no preview window.
- `--codec yuv420`: the frames are **not compressed**. Each one starts with the
  brightness of every pixel (1 byte per pixel, the Y plane), followed by the
  colour. Only the brightness is used: the convolution works in grayscale, as
  with the photo.
- `-o -`: the frames go to a pipe that Python reads, not to a file.

The camera pads each row with extra bytes up to a "round" length, the
**stride**. When the video starts, the program tries the possible lengths and
keeps the one with which consecutive rows look most alike. With a wrong length
the image comes out skewed or striped.

### 2. Reader thread: receives every frame

- Reads one full frame from the pipe.
- Makes a **small copy for the screen**: the average of every 3 × 3 block,
  864 × 648 pixels, which the browser draws easily.
- Leaves the full frame in a "mailbox" and tells the worker there is a new one.

It never waits for the convolution, so the camera image stays live even with
Python, which needs about 9 seconds per frame.

### 3. Worker thread: the convolution

It runs on **the last core of the CPU**, so that the other threads do not move
it from core to core. Again and again:

1. Waits for a new frame and takes **the newest one**. Frames that arrive while
   a slow version works are skipped, so the delay does not pile up.
2. Converts the brightness bytes to the `int32` image that every version of the
   project expects.
3. Calls the chosen version **7 times on the same frame** (Python: once; see
   [the slow motion](#the-slow-motion-7-convolutions-per-frame)) **and times
   only those calls**:
   ```python
   self.funcs[name](c_img, c_out, c_k, h, w)
   ```
   It is the same function as in the benchmark (Part 9) and the race (Part 10),
   on an image of the same size and with the same kernel.
4. Shrinks the output for the screen, keeping the **strongest edge** of every
   3 × 3 block so thin lines do not disappear, and maps it to black and white:
   no edge is white, a strong edge is black.
5. Leaves the image in another mailbox and starts again.

### 4. The helpers in C: `src/stream.c`

Converting 5 million pixels with Python loops would take longer than the
convolution itself. The three conversions are in C, so the times of the table
are the times of the versions, not of the conversions:

| Function | What it does |
|---|---|
| `gray_small` | Camera frame → small image for the screen (average of each block) |
| `y_to_i32` | Camera brightness (bytes) → `int32` image for the version |
| `edges_small` | Output of the version → small black-and-white image (strongest edge of each block) |

`make` builds them into `build/libconv_stream.so`.

### 5. Web server and page

A notebook cannot play video, but it can show a web page inside a cell:

- Python starts a small web server, **on this Pi only** (`127.0.0.1`): no other
  computer can open it.
- The cell shows the page in a frame (an *iframe*). The same address also works
  in its own browser tab.
- The page asks the server for images in a loop. The server **waits until it has
  something new** and replies with the small images it has not sent yet and the
  data of the table.
- The page draws the images on two `<canvas>` and updates the table.
- The buttons send the choice to the server, and the worker uses it on the next
  frame.

### Total time of a frame

The table shows the time of the convolution only. The worker also does the two
conversions of steps 2 and 4, a few milliseconds per frame. So:

- **Max. frames/s (real)** is 1 ÷ the time of one convolution: an upper limit.
- **Max. frames/s in this video** is that number ÷ 7 (Python: not divided).
- The frames per second in the title of the edges are the ones measured in the
  video and include the conversions, so they are a little lower.

Between the moment the camera takes a frame and the moment you see it there
are also the transfer through the pipe (7.5 MB per frame), the reply to the
page and the drawing. They add some tens of milliseconds of **delay**, but not
fewer frames per second: every step works at the same time as the others, like
an assembly line.

## Why the video stops at 15 frames per second

At 2592 × 1944 the camera gives **at most about 15 frames per second**. It is a
limit of the sensor at that size, not of the Pi or the code. A version that
needs less than about 67 ms per frame finishes before the next frame arrives and
waits for it, so every fast version shows 15 frames per second.

With the times of the benchmark (Part 9) on a Pi 5:

| Version | One convolution | Could process | It would show with one convolution per frame |
|---|---|---|---|
| Python | about 8.7 s | 0.1 frames/s | 0.1 frames/s |
| ASM v1 | 141 ms | 7 frames/s | about 7 |
| C v1 / C v2 | 63–69 ms | about 15 frames/s | 13 to 15 |
| ASM v2 / ASM v3 | 19 ms | 52 frames/s | **15** (camera limit) |
| ASM v4 NEON | 9.5 ms | 105 frames/s | **15** (camera limit) |

With one convolution per frame, the video of ASM v2, v3 and v4 would look the
same. That is why the video runs in slow motion.

A smaller size does not help: with 4 times fewer pixels the camera goes faster,
but every version is also 4 times faster, and the differences hide again at the
new limit. The screen is another limit: it draws at most 60 frames per second.

## The slow motion: 7 convolutions per frame

So that the differences show in the video of the edges, the video is **always in
slow motion**, at the full size of 2592 × 1944:

- Every camera frame goes through the version **7 times in a row**, as if the
  image were 7 times larger. Python runs once: 7 times would take a minute per
  frame.
- Only the convolution is repeated: the conversions run once per frame, so the
  difference comes only from the code of each version.
- Every frame rate of C and assembly is divided by 7, and the **proportions
  between them stay the real ones**, like a slow-motion replay of a race.

**Why 7:** the camera sends a frame every 67 ms and one convolution of ASM v4
takes 9.5 ms, so about 7 fit in a frame. ASM v4 just keeps up with the camera and
all the others fall below it. With fewer, the fastest versions look the same
again; with more, everything is slower and nothing new shows.

The frames per second are not set by the program: they are what each version
actually reaches with that work. With the times of the table above:

| Version | Work per frame | You see |
|---|---|---|
| ASM v4 NEON | about 67 ms | about 14 frames/s, smooth |
| ASM v2 / ASM v3 | about 133 ms | about 7 frames/s, it jumps |
| C v1 / C v2 | about 450 ms | about 2 frames/s, in steps |
| ASM v1 | about 1 s | about 1 frame/s, almost photos |

The video is a comparison, **not the real speed** of each version. The real
values are in the table of the page: **Time per convolution** and **Max. frames/s
(real)** are for one convolution, and *Keeps up with the camera?* uses those real
frame rates.

## Threads, cores and the GIL

| Who | What it does |
|---|---|
| Reader thread (Python) | Receives the frames and makes the small copy |
| Worker thread (Python + the version) | The convolution, on the last core |
| Server threads (Python) | One listens; another answers each request of the page |
| `rpicam-vid` | A separate program that drives the camera |
| The browser | Draws the page, in its own process |

**The GIL** (*Global Interpreter Lock*): in Python only one thread at a time can
run Python code; the threads take turns, every 5 ms. A thread lets the others
run while it waits for data (the camera pipe, the network) and while it runs a
C or assembly function called with `ctypes`. So the convolution, the
conversions and the camera **do run in parallel**, on different cores.

This means:

- **C and assembly are not slowed down by Python.** During the call, the core
  runs only the instructions of the version. Changing the version only changes
  which function is called on the next frame.
- **The core of the worker is not reserved.** The worker always runs on the last
  core, but Linux can put other programs there too. With 4 cores and the rest of
  the work being light, it stays almost free.
- **Memory is shared.** The RAM and the L3 cache are the same for all cores, and
  the camera writes about 113 MB/s into memory. A version can take a little
  longer in the video than in the benchmark of Part 9.
- **Python does compete.** The Python version is Python code, so it holds the GIL
  most of the time: while it runs, the camera image can be a little less smooth.

### Rebuilt versions: `conv_bench.load()`

The notebook loads each version from its library in `build/`. Loading a path
again would give back the library already in memory, even after `make` rebuilt
it: the race and the video would keep running the old code (for example, the
empty template). `load()` checks the time of the last build of the library and,
when it changed, loads a copy under a new name, so it always runs the code you
built last.

## Options

In the notebook, `notebook_stream()` accepts:

| Option | Default | What it does |
|---|---|---|
| `width`, `height` | `2592`, `1944` | Size of the camera frames |
| `framerate` | `15` | Frames per second asked of the camera |
| `shrink` | `3` | The images of the page are this many times smaller than the frames |
| `stride` | detected | Length of a camera row in bytes, if the detection fails |
| `port` | free one | Port of the page |

From a terminal: `python3 conv_stream.py --port 8000 --framerate 15`, and
`--stride` if needed.

## Files of this branch

| File | What changes |
|---|---|
| `conv_stream.py` | New: the camera, the threads, the web server and the page |
| `src/stream.c` | New: the three conversions in C |
| `Makefile` | Builds `build/libconv_stream.so` |
| `conv_bench.py` | `load()` loads a library again after `make` rebuilds it |
| `project.ipynb` | New Part 10b with the video |

## Troubleshooting

| Problem | Solution |
|---|---|
| The camera image is skewed or striped | The row length was not detected. Stop the video and start it with the row length, for example `notebook_stream(stride=2624)`. |
| `The camera did not start the video` | Another program or another video cell is using the camera. Run `stream.stop()`, or restart the kernel. |
| A version is missing from the buttons | It is not finished, not correct or not built: run its cell (Part 3, 5 or 7) again, then restart the video. |
| The edges freeze with one version | The notebook runs an old build of it. Update the branch (`git pull`) and restart the kernel. |
| `make` shows an error in `src/stream.c` | Check that you are on this branch and run `make` again; send the error to your instructor. |
| `libconv_stream.so not found` | Run `make` in the project folder. |
