# 2D Convolution on the Raspberry Pi: Python → C → Assembly

Mini project: you run the same operation, a 2D convolution, in Python, in C and
in ARM64 assembly on a Raspberry Pi 5, write three of the versions yourself,
and measure how fast each one is.

Everything happens in the notebook **`project.ipynb`**. This guide takes you,
step by step, from a new Raspberry Pi to the notebook, and then to handing in
your work.

- [What you need](#what-you-need)
- [Part A. Prepare the Raspberry Pi](#part-a-prepare-the-raspberry-pi)
- [Part B. Every time you work on the project](#part-b-every-time-you-work-on-the-project)
- [Part C. Work through the notebook](#part-c-work-through-the-notebook)
  - [Live video (Part 10b)](#live-video-part-10b)
- [Part D. Hand in](#part-d-hand-in)
- [Part E. Return the Raspberry Pi](#part-e-return-the-raspberry-pi)
- [Troubleshooting](#troubleshooting)

Type every command in a **terminal** on the Raspberry Pi (menu → Accessories
→ Terminal). Copy one line at a time, press **Enter**, and wait until it
finishes before the next one. Lines that start with `#` are comments: do not
type them.

> **To paste in the terminal, press Ctrl + Shift + V.** Ctrl + V does not
> paste there.

## What you need

- A Raspberry Pi 5, its power supply, and a heatsink or fan.
- A microSD card with Raspberry Pi OS (64-bit).
- A Raspberry Pi camera and a **Pi 5 camera cable** (one end narrower than the
  other).
- A screen, keyboard and mouse for the Pi.
- An internet connection (Wi-Fi or cable).

## Part A. Prepare the Raspberry Pi

The first time a new Raspberry Pi starts, it asks you to create a user. Use
these values:

- **Username:** `raspberry-` followed by the Board ID in the CanaKit box, for example `raspberry-73`.
- **Password:** `123456`.

### Step 1. Connect the camera, with the Pi off

The Pi only detects the camera when it starts, so connect it **before**
powering the Pi on.

1. If the Pi is on, shut it down (`sudo shutdown now`) and **unplug it**.
2. Find one of the two small connectors marked **CAM/DISP 0** or
   **CAM/DISP 1** on the Pi.
3. Lift the connector's latch, push the narrow end of the cable in all the way
   with its metal contacts facing the metal contacts of the connector, and
   press the latch down.
4. Do the same at the camera end, with the wide end of the cable.
5. Connect the screen, keyboard and mouse, and power the Pi on.
6. If the Pi shows the **Welcome to Raspberry Pi** wizard, follow it: choose
   your country and language, create the **user and password** given at the
   start of Part A (`sudo` asks for this password), and connect to the
   Wi-Fi. If it offers to update the software, you can skip it. When the
   wizard finishes, the Pi restarts with your user.

### Step 2. Check the system and the camera

```sh
uname -m
```

It must print **`aarch64`**. If it prints `armv7l` or `armv6l`, the system is
32-bit and the project cannot run on it: ask your instructor for a
microSD card with Raspberry Pi OS (64-bit).

```sh
rpicam-hello --list-cameras
```

It must list a camera, for example `0 : ov5647 [2592x1944 ...]`. If it says
`No cameras available!`, shut the Pi down, unplug it, check the cable at both
ends (Step 1), and power it on again.

### Step 3. Install the tools

```sh
sudo apt update
sudo apt install -y git build-essential python3-venv
```

It asks for your password. Nothing appears while
you type it: that is normal.

### Step 4. Download the project

```sh
cd ~
git clone https://github.com/eTechLab-UPRM/Assembly-with-Raspberry-PI-5.git
cd Assembly-with-Raspberry-PI-5
```

Build the code and test it:

```sh
make
python3 conv_bench.py --test
```

The last line must end in **`all OK`**. Two lines say `MISMATCH`: that is
expected, they are the versions you write later in the notebook.

### Step 5. Install Jupyter

```sh
python3 -m venv ~/jupyter-env
~/jupyter-env/bin/pip install --index-url https://pypi.org/simple --resume-retries 5 --timeout 60 notebook
```

It downloads about 100 packages and can take several minutes. It must end with
a line that starts with `Successfully installed` and includes `notebook`. If
the download stops with an error, run the same command again: it continues
where it stopped.

The Raspberry Pi is ready. Go on to Part B.

## Part B. Every time you work on the project

1. Power the Pi on (with the camera already connected) and open a terminal.
2. Open the notebook:

   ```sh
   cd ~/Assembly-with-Raspberry-PI-5
   ~/jupyter-env/bin/jupyter notebook project.ipynb
   ```

   The notebook opens in the browser.

> [!CAUTION]
> **Always open the notebook from the terminal, with the two commands above.**
> Do not open `project.ipynb` by double-clicking it.
>
> **Do not close that terminal while you work.** It is running Jupyter: if you
> close it, the notebook stops working and you can lose what you have not
> saved. Close it only at the end (point 4).

3. Work in the notebook (Part C). Save often with **Ctrl + S**.
4. When you finish for the day: save the notebook, go back to the terminal,
   press **Ctrl + C**, then `y` and **Enter**.

Your work is kept in the notebook file: next time, repeat these steps and
continue where you left off.

## Part C. Work through the notebook

- Run the cells **in order, from top to bottom**: click a cell and press
  **Shift + Enter**.
- Read every text cell: it explains what the next code cell does and what to
  look at in its output.
- The questions are the cells marked **✏️ Q#** (Q for *question*: ✏️ **Q1**
  to ✏️ **Q9**). **Your answer goes in the cell immediately below the
  question**, marked **ANSWER Q# HERE**: double-click it, write your answer,
  then press Shift + Enter. Do not write in the question cell.
- In **Parts 3, 5 and 7** you write code inside a cell (one C function and two
  pieces of assembly). Write it in the cell and run the cell: it builds and
  checks your code. It is correct when the cell says **`check: OK`**. If it
  says `NOT BUILT`, the message shows the line of your code with the error.
- Made a mess in an exercise cell? **Ctrl + Z** in the cell undoes your edits.
- Measure with other programs closed: times change if the Pi is busy.

The notebook has these parts:

| Part | What you do |
| --- | --- |
| 0 | Check the setup |
| 1 | See a convolution, compute one pixel by hand, take your photo |
| 2 | Measure Python and C v1 |
| 3 | **Write C v2** and see why the loop order matters |
| 4 | Read the RISC-V (Ripes) → ARM64 translation tables |
| 5 | **Write the core of assembly v1** |
| 6 | Measure assembly v2 (pointers) |
| 7 | **Write assembly v3** with the MAC instruction `madd` |
| 8 | Measure assembly v4 (NEON) |
| 9 | Measure all the versions together |
| 10 | Watch the race |
| 10b | Watch the convolution on live video (a demonstration) |
| 11 | Write your conclusions |

### Live video (Part 10b)

This part is a demonstration: it has no questions and you write no code. It
applies the convolution to live video from the camera, at the same resolution as
your photo (2592 × 1944 pixels).

1. Run the cell of Part 10b. The camera appears on the left and its edges on the
   right.
2. Choose a version with the buttons. The table shows the measured time of one
   convolution and how many frames per second each version could process.
3. Click **Stop video** when you are done. No other cell can use the camera until
   you do.

- **Buttons:** the versions you write (C v2, ASM v1 and ASM v3) only get a button
  once their code is complete and correct. If you finish one while the video is
  running, stop the video and run the cell again.
- **Slow motion:** the camera delivers at most 15 frames per second, so any
  version faster than that would look the same. To make the differences visible,
  each camera frame is convolved 7 times (Python: once).
- **Hand-in:** the video is not saved in the notebook file. That is normal.

## Part D. Hand in

Hand in **only the notebook**, as an `.ipynb` file named with your full name and
no spaces: **`NombreCompleto.ipynb`** (for example, `JuanPerezRivera.ipynb`).

1. Check that every code cell has its output and every **ANSWER Q# HERE**
   cell has your answer.
2. Save the notebook (**Ctrl + S**).
3. Download it: **File → Download**. The browser saves `project.ipynb` in
   `~/Downloads`.
4. In `~/Downloads`, rename the downloaded file to `NombreCompleto.ipynb`, with
   your own full name. Do not rename `project.ipynb` in the project folder: the
   commands of Part B open it by that name.
5. Upload that file to Moodle.

## Part E. Return the Raspberry Pi

When your work is in Moodle, return the Raspberry Pi as you received it. This
step **erases everything** on the Pi and cannot be undone, so do it only
after Part D.

1. Close Jupyter (Part B, point 4) and the browser.
2. In a terminal, run:

   ```sh
   sudo ~/Assembly-with-Raspberry-PI-5/factory_reset.sh
   ```

3. It lists what it will erase. Type `ERASE` and press **Enter**.
4. The Pi restarts, erases everything (it can take a few minutes) and
   **powers off by itself**. Do not unplug it before the screen goes dark
   and the green light stops blinking.
5. Unplug it and return it with the camera, the cable and the SD card.

The next time the Pi starts, it shows the welcome wizard, as a new Raspberry
Pi.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `rpicam-hello --list-cameras` says `No cameras available!` | Shut the Pi down, unplug it, check that the cable is the Pi 5 type and fully inserted at both ends with the latches closed, and power it on again (Step 1). |
| The notebook says `No camera detected` | Same as above, then run the photo cell of Part 1 again. |
| The notebook says the camera did not take the photo | Close any other program using the camera, run `rpicam-hello --list-cameras` in a terminal, and run the photo cell again. |
| `photo.pgm not found` | Take the photo first: run the photo cell in Part 1. |
| `uname -m` prints `armv7l` or `armv6l` | The system is 32-bit. Ask your instructor for a microSD card with Raspberry Pi OS (64-bit). |
| `git clone` asks for a username and password | The repository address is wrong or private. Check the address with your instructor. |
| `pip install` fails with `incomplete-download` | Slow connection. Run the Step 5 command again; it continues where it stopped. |
| `pip` says `no such option: --resume-retries` | Old `pip`. Run `~/jupyter-env/bin/pip install --upgrade pip` and repeat Step 5. |
| `jupyter: No such file or directory` | Use the full path `~/jupyter-env/bin/jupyter` (Part B), or install Jupyter (Step 5). |
| An exercise cell says `NOT BUILT` | A mistake in your code. The message shows the line and what is wrong: fix it in the cell and run the cell again. |
| An exercise cell says `MISMATCH` | Your code builds but computes a wrong result. In Parts 3 and 5, check the loop limits and the indexes; in Part 7, check the order of the `madd` operands. |
| An exercise cell says your code *never ends* or *crashed the program* | A loop never reaches its limit (a counter not increased, or a jump to the wrong label), or an index goes outside the image. Fix the code and run the cell again. |
| A row of the table in Part 9 says `NOT BUILT` | Run `make` in a terminal and read its error. |
| Part 10b: a version you wrote has no button | Its code is not complete or not correct. Run its cell (Part 3, 5 or 7) until it says `check: OK`, stop the video and run the Part 10b cell again. In Part 7, also replace every `TODO` pair with `madd`. |
| Part 10b says `The camera did not start the video` | Another cell or program is using the camera. Click **Stop video** or run `stream.stop()`; if it continues, restart the kernel (**Kernel → Restart**). |
| Part 10b: the camera image is skewed or striped | The row length was not detected. Click **Stop video** and run the cell with the row length, for example `stream = notebook_stream(stride=2624)`. |
| Part 10b says `libconv_stream.so not found` | Run `make` in a terminal and read its error. |
| Times look much slower than expected | Close other programs, check the heatsink or fan, and run `vcgencmd get_throttled`: `throttled=0x0` means the CPU is not being slowed down by heat or power. |
