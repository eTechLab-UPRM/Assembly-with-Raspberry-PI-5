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
- [Part D. Hand in](#part-d-hand-in)
- [Part E. Return the Raspberry Pi](#part-e-return-the-raspberry-pi)
- [Troubleshooting](#troubleshooting)

Type every command in a **terminal** on the Raspberry Pi (menu → Accessories
→ Terminal). Copy one line at a time, press **Enter**, and wait until it
finishes before the next one. Lines that start with `#` are comments: do not
type them.

## What you need

- A Raspberry Pi 5, its power supply, and a heatsink or fan.
- A microSD card with Raspberry Pi OS (64-bit).
- A Raspberry Pi camera and a **Pi 5 camera cable** (one end narrower than the
  other).
- A screen, keyboard and mouse for the Pi.
- An internet connection (Wi-Fi or cable).

## Part A. Prepare the Raspberry Pi

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
   your country and language, create **your user and password** (remember
   them: `sudo` asks for this password), and connect to the Wi-Fi. If it
   offers to update the software, you can skip it. When the wizard
   finishes, the Pi restarts with your user.

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

   The notebook opens in the browser. **Leave the terminal open** while you
   work: it is running Jupyter.
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
- A cell marked **✏️** is a question: double-click it, write your answer
  below **Your answer:**, then press Shift + Enter.
- In **Parts 3, 5 and 7** you write code inside a cell (one C function and two
  pieces of assembly). Write it in the cell and run the cell: it builds and
  checks your code. It is correct when the cell says **`check: OK`** and the
  *extra check* below it is OK too. If it says `NOT BUILT`, the message shows
  the line of your code with the error.
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
| 11 | Write your conclusions |

## Part D. Hand in

1. Check that every code cell has its output and every ✏️ question has your
   answer.
2. Save the notebook (**Ctrl + S**).
3. Export it: **File → Save and Export Notebook As… → HTML**. The browser saves
   an `.html` file in `~/Downloads`.
4. Open the HTML file to check that your answers, your photo and the outputs
   are there.
5. Upload the HTML file to Moodle.

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
| Times look much slower than expected | Close other programs, check the heatsink or fan, and run `vcgencmd get_throttled`: `throttled=0x0` means the CPU is not being slowed down by heat or power. |
