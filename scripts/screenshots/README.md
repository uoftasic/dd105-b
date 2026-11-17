# Waveform screenshots

`shoot.sh` renders a PNG of a waveform as it looks in Surfer or GTKWave, the two waveform
viewers in the course image. It starts the viewer in Docker with a virtual X display (no
monitor needed), opens the file at a fixed window size, and trims the picture below the last
trace. A rerun with the same inputs writes the same bytes. Use it for the waveform figures in
`docs/assets/img/`.

| File | What it is |
|------|------------|
| `shoot.sh` | Run this on the host. It starts the screenshot image and runs `waveshot.py` in it. |
| `waveshot.py` | Does the work inside the container: Xvfb, the viewer, the capture and the crop. |

## Requirements

Docker, and the screenshot image `asic-edu/shot-rig:2026.08` on the machine. That image is the
course workbench image `hpretl/iic-osic-tools:2026.08` with the tools for headless screenshots
added, so Surfer 0.7.0, GTKWave v4.0.0-prealpha (132a086) and their fonts are the ones students
run. It is a local image; no Dockerfile for it is committed anywhere. Its build history
(`docker history --no-trunc asic-edu/shot-rig:2026.08`) comes to this, if you need to rebuild it:

```dockerfile
FROM hpretl/iic-osic-tools:2026.08
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb x11-apps x11-utils xdotool wmctrl imagemagick \
      fonts-dejavu-core fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
      sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml; \
    fi
USER 1000
```

`asic-edu/gui-rig:2026.08` is built on top of it (it adds `fluxbox`, `xterm` and
`x11-xserver-utils`), so it works too: `SHOT_IMAGE=asic-edu/gui-rig:2026.08`.

## Commands

Run these from the repo root. `shoot.sh` mounts the directory you run it from at `/w` in the
container, so the waveform and the PNG must both be under it, given as relative paths.

The examples use a waveform from an ALU testbench, `build/alu.fst`, with the top module
`alu_tb_top`, the ALU instance `u_alu` and the interface instance `aif`. Put your own file and
signal names in their place.

List the signal names in a file:

```bash
scripts/screenshots/shoot.sh surfer build/alu.fst --list
```

Surfer, chosen signals, the first 300 ns:

```bash
scripts/screenshots/shoot.sh surfer build/alu.fst \
  -s alu_tb_top.clk,aif.rst_n,aif.in_valid,aif.op,aif.a,aif.b,aif.out_valid,aif.result,aif.carry,aif.zero \
  --from 0ns --to 300ns \
  -o docs/assets/img/alu-first-ops.png
```

The ALU FST has a 1 ps tick, so Surfer's time ruler reads `20000 ps`, `40000 ps` and so on.
`--time-unit ns` makes it read `20 ns`, `40 ns`:

```bash
scripts/screenshots/shoot.sh surfer build/alu.fst \
  -s alu_tb_top.clk,aif.in_valid,aif.op,aif.a,aif.b,aif.out_valid,aif.result,aif.carry,aif.zero \
  --from 80ns --to 160ns --time-unit ns \
  -o docs/assets/img/alu-sub-borrow.png
```

Surfer with a command file, as in `surfer -c view.sf`, over the whole run. `scope_add` is
Surfer's command for adding every signal in a scope:

```bash
printf 'scope_add alu_tb_top.aif\n' > view.sf
scripts/screenshots/shoot.sh surfer build/alu.fst -c view.sf -o docs/assets/img/alu-aif.png
```

GTKWave, chosen signals, the first 300 ns:

```bash
scripts/screenshots/shoot.sh gtkwave build/alu.fst \
  -s alu_tb_top.clk,aif.rst_n,aif.in_valid,aif.op,aif.a,aif.b,aif.out_valid,aif.result,aif.carry,aif.zero \
  --from 0ns --to 300ns \
  -o docs/assets/img/alu-first-ops-gtkwave.png
```

GTKWave with the signal list from a `.gtkw` save file, over the whole run:

```bash
scripts/screenshots/shoot.sh gtkwave build/alu.fst -a alu.gtkw -o docs/assets/img/alu-gtkwave.png
```

Each run ends by printing the PNG's path, its width and height in pixels, and the first 16
hex digits of its SHA-256, which you can compare between runs:

```
waveshot: wrote docs/assets/img/alu-first-ops.png (1400x305, sha256 b4b6240c92da24c1...)
```

A Surfer run takes about 5 s, or 14 s with `--time-unit`, which starts Surfer twice. A GTKWave
run takes about 7 s, or about 11 s when GTKWave has to be started a second time to correct
the zoom (see step 4 below).

`shoot.sh` reads two environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SHOT_IMAGE` | `asic-edu/shot-rig:2026.08` | The image to run in. |
| `SHOT_LOCK` | unset | A lock file. When it is set, `shoot.sh` holds it with `flock` while the container runs. Point it at the same file as your other container jobs on a shared machine and they take turns. |

The container gets 2 CPUs, 3 GB of memory and no network, and runs with your user and group
id, so you own the PNG it writes.

## Arguments

`shoot.sh VIEWER WAVE [options]`, where `VIEWER` is `surfer` or `gtkwave`.

| Argument | Default | Meaning |
|----------|---------|---------|
| `WAVE` | | The FST or VCD file. |
| `-o`, `--out PNG` | | The PNG to write. Its folder is created if needed. |
| `-s`, `--signals NAMES` | | Signals to show, top to bottom, separated by commas or spaces. Repeat the option to add more. A name can be the full path (`alu_tb_top.aif.op`) or any ending of it that matches one signal only (`aif.op`). A bit range at the end (`op[2:0]`) is ignored. A name that matches no signal, or more than one, stops the run with the candidates listed, so a typo can't leave an empty row in the picture. |
| `-c`, `--command-file FILE` | | Surfer only. A Surfer command file, the same as `surfer -c FILE`. Its commands run first, then any `--signals`. |
| `-a`, `--save FILE` | | GTKWave only. A `.gtkw` save file whose signal list to use. Its dump file, size, position, start time and zoom are replaced. |
| `--from TIME` | start of the file | Left edge of the time window. |
| `--to TIME` | end of the file | Right edge of the time window. |
| `--time-unit UNIT` | the file's unit | Surfer only. The unit of the time ruler: `fs`, `ps`, `ns`, `us`, `ms`, `s` or `auto`. Without it the ruler is in the file's own unit, which is what Surfer shows when you open the file yourself. |
| `--width PX` | 1400 | Window width, which is also the PNG width. |
| `--height PX` | 900 | Window height before trimming. Raise it if the run warns that the traces reach the bottom. |
| `--crop MODE` | `auto` | `auto` trims the picture `--pad` px below the last trace. `none` keeps the whole window. A rectangle `WxH+X+Y`, such as `1400x200+0+0`, cuts that part out of the window. |
| `--pad PX` | 25 for Surfer, 11 for GTKWave | Space kept under the last trace with `--crop auto`. |
| `--theme NAME` | Surfer's default dark theme | Surfer only. One of Surfer's built-in themes, such as `light+`. |
| `--hide-side-panel` | off | Surfer only. Hides the panel on the left that lists scopes and variables, which gives the waves about 300 px more. |
| `--settle S` | 1.0 | Seconds to wait after the viewer is ready before grabbing frames. The picture is taken once four grabs in a row are identical. |
| `--timeout S` | 90 | Give up after this many seconds at any step. |
| `--list` | | Print every signal name in the file and exit. |
| `--keep DIR` | | Use `DIR` as the scratch folder and leave it behind: the viewer's log, the generated Surfer command file (`view.sucl`) or `.gtkw`, and `full.png`, the whole window before trimming. |

`TIME` is a number with a unit (`fs`, `ps`, `ns`, `us`, `ms`, `s`), such as `120ns` or
`1.5us`, or a bare number of the file's ticks. It has to come to a whole number of ticks.
Without `--from` and `--to`, Surfer opens on the whole run, unless the command file zooms, and
GTKWave is zoomed to fit the whole run. Give only one of the two and the other is the file's
start or end.

## Size, theme and framing

The defaults copy the waveform figures DD104 publishes (`dd104/docs/assets/img/surfer-counter.png`
and `gtkwave-counter.png`), so DD105-A's figures look like them. That means the viewer's window
alone, with no title bar or border, starting at its menu bar; the viewer's default theme
(dark for Surfer, light for GTKWave); the side panels showing; 1400 px wide; and 25 px (Surfer)
or 11 px (GTKWave) kept below the last trace.

The DD104 GTKWave figure is 1032 px wide, but the GTKWave in the 2026.08 image won't open a
window narrower than 1374 px, so GTKWave uses 1400 px like Surfer. If you ask for less than
1374, the run warns and the PNG comes out 1374 px wide.

## What waveshot.py does

1. It reads the waveform header (through `fst2vcd` for FST) for the timescale, the time span
   and the signal names, and checks every `--signals` name against them.
2. It starts Xvfb, a virtual X display, at 96 dpi and with no window manager, so the viewer's
   window has no title bar. The display is larger than the window, and the pointer sits
   outside the window, so the viewer shows no hover highlight or tooltip.
3. The viewer runs with an empty home folder and config, from an empty folder, so no
   personal or project settings reach the picture. Surfer gets a config that sets the window
   size, turns animations off, and turns off two prompts (to load a saved state found next to
   the waveform, and to reload a waveform that changed on disk).
4. For Surfer, it writes a command file (yours, then the `--signals` as `variable_add` lines)
   and connects to Surfer over WCP, the control protocol Surfer listens on. It waits until
   Surfer lists the signals, then sends `set_viewport_range`, which puts `--from` at the left
   edge of the wave area and `--to` at the right edge. Surfer has no command for the ruler's
   unit, so for `--time-unit` it first runs Surfer once to save a state file, changes the unit
   in that file, and opens the state.

   For GTKWave, it writes a `.gtkw` save file with the window size, the start time and a zoom
   level. GTKWave's zoom `z` shows 2^-z ticks across 200 px, so the zoom that makes the window
   end at `--to` depends on how wide the wave pane is. The script measures the pane in the
   first picture, and if it differs from its estimate, starts GTKWave again with the zoom
   corrected.
5. It grabs the screen with `xwd` until four grabs in a row, 0.3 s apart, are identical. It
   finds the last trace by counting the drawn pixels in each row of the wave area, cuts `--pad`
   px below it, and writes an RGB PNG with Pillow. The PNG has no timestamp, text or other
   optional chunks, the same as the DD104 PNGs.

## Rerunning

The same image, waveform and arguments give the same PNG, byte for byte, so `sha256sum` or
`cmp` tells you whether a rerun changed a figure. A different Surfer or GTKWave version, image
tag or window size changes the picture.

This was checked on a 40-transaction run of the ALU testbench: five runs of the first Surfer
example all printed `sha256 b4b6240c92da24c1`, and so did a run on a VCD copy of the same
waveform. Two runs of the GTKWave example both printed `sha256 998d3bb9cbc073f4`.

## FST tracing with Verilator in the 2026.08 image

Verilator 5.050 in `hpretl/iic-osic-tools:2026.08` can't build a model with `--trace-fst`. Its
FST writer includes `<lz4.h>` and links with `-llz4`, and the image has the LZ4 runtime
library (`liblz4.so.1`) but not the `liblz4-dev` package with the header. The C++ build stops
with `fatal error: lz4.h: No such file or directory`.

Two ways around it, short of adding `liblz4-dev` to the image:

- Trace with `--trace-vcd` instead. `shoot.sh` reads VCD, and `vcd2fst` in the image converts
  VCD to FST.
- Give Verilator the header and the link name itself. The writer calls only
  `LZ4_compressBound` and `LZ4_compress_default`. Make a folder, say `lz4shim/`, with this
  `lz4.h`:

  ```c
  #ifndef LZ4_SHIM_H
  #define LZ4_SHIM_H
  #ifdef __cplusplus
  extern "C" {
  #endif
  int LZ4_compressBound(int inputSize);
  int LZ4_compress_default(const char* src, char* dst, int srcSize, int dstCapacity);
  #ifdef __cplusplus
  }
  #endif
  #endif
  ```

  and a link to the runtime library next to it:

  ```bash
  ln -s /usr/lib/x86_64-linux-gnu/liblz4.so.1 lz4shim/liblz4.so
  ```

  Then add `-CFLAGS -I$PWD/lz4shim -LDFLAGS -L$PWD/lz4shim` to the `verilator` command. The
  ALU waveform used to test this tool was built this way.
