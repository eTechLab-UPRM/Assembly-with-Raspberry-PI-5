# Setup Guide: from a New Raspberry Pi to the Project Notebook

Follow these steps once on your Raspberry Pi. They take about 20–30 minutes,
most of it waiting for downloads. When you finish, you will have the project
notebook (`project.ipynb`) open in the browser.

Type every command in a **terminal** on the Pi (menu → Accessories →
Terminal, or connect over SSH). Lines that start with `#` are comments: you
do not need to type them.

## What you need

- A Raspberry Pi 5 (a Pi 4, 3 or Zero 2 W also works, only slower).
- A microSD card of 16 GB or more, the power supply, and a heatsink or fan.
- An internet connection (Wi-Fi or cable).
- A Raspberry Pi camera with a Pi 5 camera cable. The project works on a photo
  taken with it, so the camera is required.
- A computer with [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
  to prepare the SD card, if the Pi does not have a system yet.

## Step 1. Install Raspberry Pi OS (64-bit)

Skip this step if your Pi already starts into Raspberry Pi OS **64-bit**
(check it in Step 2).

1. Open Raspberry Pi Imager on your computer and insert the microSD card.
2. **Device:** your Raspberry Pi model.
3. **Operating system:** *Raspberry Pi OS (64-bit)*. Do not choose the
   32-bit version: the assembly code of this project is for 64-bit ARM.
4. **Storage:** the microSD card.
5. When Imager offers to customize the settings, set a username and
   password, your Wi-Fi network, and (optional) enable SSH.
6. Write the card, put it in the Pi and power it on. The first start takes a
   few minutes.

## Step 2. Check that the system is 64-bit

```sh
uname -m
```

It must print **`aarch64`**. If it prints `armv7l` or `armv6l`, the system
is 32-bit: go back to Step 1 and install the 64-bit version.

## Step 3. Install the tools

```sh
sudo apt update
sudo apt install -y git build-essential python3-venv
```

- `git` downloads the project files.
- `build-essential` brings `gcc` (the C compiler and ARM assembler) and
  `make`.
- `python3-venv` lets you install Jupyter in its own folder (Step 5).

Python 3 is already part of Raspberry Pi OS.

## Step 4. Download the project

```sh
cd ~
git clone https://github.com/kevinnt16/Assembly-with-Raspberry-PI-5.git
cd Assembly-with-Raspberry-PI-5
```

If `git` asks for a username and password, the repository is private: ask
your instructor for access.

Build the code and run the correctness test to check that everything works:

```sh
make
python3 conv_bench.py --test
```

The last line must end in **`all OK`**.

## Step 5. Install Jupyter

Raspberry Pi OS does not allow installing Python packages for the whole
system with `pip`, so Jupyter goes into its own folder (a *virtual
environment*) at `~/jupyter-env`:

```sh
python3 -m venv ~/jupyter-env
~/jupyter-env/bin/pip install --index-url https://pypi.org/simple --resume-retries 5 --timeout 60 notebook
```

This downloads about 100 packages and can take several minutes. It must end
with a line that starts with `Successfully installed` and includes
`notebook`.

Why the extra options:

- `--index-url https://pypi.org/simple` downloads from PyPI directly. The
  default mirror for the Pi (piwheels.org) can be very slow and cut the
  download in the middle.
- `--resume-retries 5` continues an interrupted download instead of failing.
- `--timeout 60` waits longer on a slow connection.

If the download still fails, run the same command again: the packages that
already downloaded are kept.

## Step 6. Connect the camera

The project works on a photo taken with the Raspberry Pi camera, so this step is
required. **The camera must be connected before the Pi is powered on**: the
Pi only detects it when it starts.

1. **Shut the Pi down and unplug it** (`sudo shutdown now`). Connecting the
   camera while the Pi is on does not work.
2. On a Raspberry Pi 5 the camera goes into one of the two small connectors
   marked **CAM/DISP 0** or **CAM/DISP 1**. The Pi 5 connectors are smaller
   than on older models, so the camera needs a **Pi 5 camera cable** (one end
   narrower than the other).
3. Lift the latch of the connector, push the cable in all the way with its
   metal contacts facing the metal contacts of the connector, and press the
   latch down. Do the same at the camera end.
4. Power the Pi on and check that it sees the camera:

```sh
rpicam-hello --list-cameras
```

It must list a camera, for example `0 : ov5647 [2592x1944 ...]`. If it says
`No cameras available!`, go back to point 1. Take a test photo and open
`~/test.jpg` in the file manager:

```sh
rpicam-still -n -o ~/test.jpg
```

## Step 7. Open the project notebook

```sh
cd ~/Assembly-with-Raspberry-PI-5
~/jupyter-env/bin/jupyter notebook project.ipynb
```

The notebook opens in the Pi's browser. Leave the terminal open while you
work: it is running Jupyter. To stop Jupyter at the end, save the notebook,
go back to the terminal and press **Ctrl + C**, then `y`.

From now on, every time you want to work on the project you only repeat Step 7.

### Working from another computer (optional)

If you connect to the Pi over SSH instead of using its screen:

```sh
cd ~/Assembly-with-Raspberry-PI-5
~/jupyter-env/bin/jupyter notebook project.ipynb --no-browser --ip=0.0.0.0
```

Jupyter prints an address like `http://127.0.0.1:8888/tree?token=...`.
Open it in the browser of your computer, replacing `127.0.0.1` with the IP
address of the Pi (find it on the Pi with `hostname -I`). Both devices must
be on the same network.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `rpicam-hello --list-cameras` says `No cameras available!` | Shut the Pi down, unplug it, check that the cable is the Pi 5 type and fully inserted at both ends with the latches closed, and power it on again (Step 6). |
| The notebook says `No camera detected` | Same as above: shut down, check the cable, power on, then run the photo cell again. |
| The notebook says the camera did not take the photo | Close any other program using the camera, run `rpicam-hello --list-cameras` in a terminal, and run the photo cell again. |
| `photo.pgm not found` | Take the photo first: run the photo cell in Part 1 of the notebook (or `python3 conv_demo.py photo` in a terminal). |
| `uname -m` prints `armv7l` or `armv6l` | The system is 32-bit. Install Raspberry Pi OS (64-bit), Step 1. |
| `git clone` says `Password authentication is not supported` | The repository is private and GitHub needs a token, not a password. Ask your instructor for access. |
| `pip install` fails with `incomplete-download` | Slow connection. Run the Step 5 command again; it continues where it stopped. |
| `pip` says `no such option: --resume-retries` | Old `pip`. Run `~/jupyter-env/bin/pip install --upgrade pip` and repeat Step 5. |
| `jupyter: No such file or directory` | Jupyter is not installed yet, or you typed `jupyter` alone. Use the full path `~/jupyter-env/bin/jupyter` (Step 7). |
| Part 3, 4 or 7 says `NOT BUILT` | A mistake in your code. The message shows the line of your code and what is wrong: fix it in the cell and run the cell again. |
| A row of the table says `NOT BUILT` | That library did not build. Run `make` and read its error. |
| A row of the table says `MISMATCH` | That version computes a wrong result. In Parts 3 and 4, check the loop limits and the indexes; in Part 7, check the order of the `madd` operands. |
| An exercise cell says your code *never ends* or *crashed the program* | A loop never reaches its limit (a counter not increased, or a jump to the wrong label), or an index goes outside the image. Fix the code in the cell and run it again. |
| You want to undo your changes to an exercise | Ctrl + Z in the exercise cell undoes your edits. If a file itself is broken, `git checkout src/conv_student_c.c src/conv_student_v1.S src/conv_student.S` restores them. |
| Times look much slower than expected | Close other programs, check the heatsink or fan, and run `vcgencmd get_throttled`: `throttled=0x0` means the CPU is not being slowed down by heat or power. |

## Summary of the commands

```sh
# once
uname -m                                         # must print aarch64
sudo apt update
sudo apt install -y git build-essential python3-venv
cd ~
git clone https://github.com/kevinnt16/Assembly-with-Raspberry-PI-5.git
cd Assembly-with-Raspberry-PI-5
make
python3 conv_bench.py --test                     # must end in "all OK"
python3 -m venv ~/jupyter-env
~/jupyter-env/bin/pip install --index-url https://pypi.org/simple --resume-retries 5 --timeout 60 notebook

# check the camera (connect it with the Pi off, then power on)
rpicam-hello --list-cameras                      # must list the camera

# every time you work on the project
cd ~/Assembly-with-Raspberry-PI-5
~/jupyter-env/bin/jupyter notebook project.ipynb
```
