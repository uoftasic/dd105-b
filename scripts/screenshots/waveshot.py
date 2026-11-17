#!/usr/bin/env python3
"""Screenshot a waveform in Surfer or GTKWave, headless, at a fixed window size.

This runs inside the screenshot rig image (asic-edu/shot-rig:2026.08): the course image
plus Xvfb, xdotool, xwd and ImageMagick. From the host, run it through shoot.sh in this
folder. README.md has the commands and what every argument means.

What it does, in order:
  1. reads the waveform's header (fst2vcd for FST) to learn the timescale, the time span
     and every signal name, so a misspelt signal stops the run instead of giving a picture
     with an empty row;
  2. starts Xvfb with no window manager, so the app has no title bar or border, and parks
     the pointer outside the app window so nothing is hovered;
  3. starts the viewer with a throwaway HOME and config, so nobody's personal settings leak
     into the picture;
  4. for Surfer, drives it over WCP (Surfer's control socket) to wait until the signals are
     on screen and to set the exact time window; for GTKWave, writes a .gtkw save file with
     the window size, start time and zoom, measures the wave pane, and relaunches once if
     the zoom needs correcting;
  5. grabs the screen until several frames in a row are identical, crops it to the app
     window and trims everything below the last trace (plus padding), and writes a PNG
     with no timestamp or other metadata.
"""
import argparse
import difflib
import hashlib
import io
import json
import math
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

# Defaults chosen to match the screenshots the other courses already publish.
# dd104/docs/assets/img/surfer-counter.png is 1400 px wide and keeps 25 px under the last trace;
# dd104/docs/assets/img/gtkwave-counter.png keeps 11 px under the last row. That one is 1032 px
# wide, but the GTKWave in the 2026.08 image will not go narrower than about 1374 px (its
# toolbar is wider), so GTKWave uses Surfer's 1400 too.
SURFER_WIDTH = 1400
GTKWAVE_WIDTH = 1400
WINDOW_HEIGHT = 900
SURFER_PAD = 25
GTKWAVE_PAD = 11
GAP_ROWS = 45          # this many rows with no trace end the signal area
INK = 60               # a pixel this far from the background in any channel is drawn ink
UNITS = {"fs": -15, "ps": -12, "ns": -9, "us": -6, "ms": -3, "s": 0}

SURFER_CONFIG = """\
# Written by waveshot.py. Everything else is Surfer's built-in default.
animation_enabled = false
autoload_sibling_state_files = "Never"
autoreload_files = "Never"
{theme}[layout]
window_width = {width}
window_height = {height}
{layout}"""

# --time-unit values and the names Surfer's state file uses for them.
SURFER_TIME_UNITS = {"fs": "FemtoSeconds", "ps": "PicoSeconds", "ns": "NanoSeconds",
                     "us": "MicroSeconds", "ms": "MilliSeconds", "s": "Seconds", "auto": "Auto"}

GTKWAVE_RC = """\
disable_tooltips 1
do_initial_zoom_fit 0
"""


class ShotError(Exception):
    pass


def say(msg, _said=set()):
    if msg not in _said:          # GTKWave can run twice; say each thing once
        _said.add(msg)
        print(f"waveshot: {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- waveform header

class WaveInfo:
    def __init__(self, path):
        self.path = path
        self.tick_exp = None   # one tick of the file is 10**tick_exp seconds
        self.start = None
        self.end = None
        self.vars = {}         # dotted name without range -> (width, "[msb:lsb]" or "")


def parse_vcd_header(lines, info):
    """Read $scope/$var/$timescale up to $enddefinitions from an iterator of text lines."""
    scope, pending = [], []
    for line in lines:
        pending.extend(line.split())
        while "$end" in pending:
            i = pending.index("$end")
            group, pending = pending[:i], pending[i + 1:]
            if not group:
                continue
            kw = group[0]
            if kw == "$scope" and len(group) >= 3:
                scope.append(group[2])
            elif kw == "$upscope" and scope:
                scope.pop()
            elif kw == "$timescale":
                m = re.fullmatch(r"(1|10|100)\s*(fs|ps|ns|us|ms|s)", "".join(group[1:]))
                if m:
                    info.tick_exp = UNITS[m.group(2)] + len(m.group(1)) - 1
            elif kw == "$var" and len(group) >= 5:
                width = int(group[2])
                name = group[4]
                rng = group[5] if len(group) > 5 and group[5].startswith("[") else ""
                m = re.fullmatch(r"(.+?)(\[\d+(?::\d+)?\])", name)
                if m and not rng:          # some writers glue the range onto the name
                    name, rng = m.group(1), m.group(2)
                info.vars[".".join(scope + [name])] = (width, rng)
            elif kw == "$enddefinitions":
                return True
    return False


def read_wave_info(path):
    info = WaveInfo(path)
    with open(path, "rb") as f:
        head = f.read(330)
    if head[:1] == b"\x00" and len(head) >= 330:          # FST header block (fstapi.c)
        info.start, info.end = struct.unpack(">QQ", head[9:25])
        info.tick_exp = struct.unpack(">b", head[73:74])[0]
        proc = subprocess.Popen(["fst2vcd", str(path)], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, errors="replace")
        try:
            ok = parse_vcd_header(proc.stdout, info)
        finally:
            proc.kill()
            proc.wait()
        if not ok:
            raise ShotError(f"fst2vcd could not read the hierarchy of {path}")
    elif path.suffix.lower() == ".vcd":
        with open(path, "r", errors="replace") as f:
            if not parse_vcd_header(f, info):
                raise ShotError(f"{path}: no $enddefinitions, is it a VCD file?")
            for line in f:
                if line.startswith("#"):
                    info.start = int(line[1:].split()[0])
                    break
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - (1 << 20)))
            times = re.findall(rb"^#(\d+)", f.read(), flags=re.M)
        if times:
            info.end = int(times[-1])
    else:
        raise ShotError(f"{path}: only FST and VCD files are supported")
    if not info.vars:
        raise ShotError(f"{path} has no signals in it")
    return info


def resolve_signals(names, info):
    """Map each requested name to a full dotted name in the file, or stop with a hint."""
    out = []
    for raw in names:
        key = re.sub(r"\s*\[\d+(?::\d+)?\]$", "", raw)
        if key in info.vars:
            out.append(key)
            continue
        hits = [v for v in info.vars if v.endswith("." + key)]
        if len(hits) == 1:
            out.append(hits[0])
            continue
        if hits:
            raise ShotError(f"signal {raw!r} matches {len(hits)} signals: "
                            + ", ".join(sorted(hits)[:8]) + ". Give more of the path.")
        close = difflib.get_close_matches(key, list(info.vars), n=5, cutoff=0.5)
        hint = ("Close names: " + ", ".join(close)) if close else \
            "Run with --list to see every name."
        raise ShotError(f"no signal named {raw!r} in {info.path}. {hint}")
    return out


def to_ticks(text, info, what):
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-z]*)\s*", text)
    if not m or (m.group(2) and m.group(2) not in UNITS):
        raise ShotError(f"{what} {text!r}: write a number of ticks, or a time such as 120ns")
    value = Decimal(m.group(1))
    if m.group(2):
        if info.tick_exp is None:
            raise ShotError(f"{info.path} states no timescale; give {what} in ticks")
        value = value * Decimal(10) ** (UNITS[m.group(2)] - info.tick_exp)
    if value != value.to_integral_value():
        raise ShotError(f"{what} {text!r} is not a whole number of the file's ticks "
                        f"(1 tick = 1e{info.tick_exp} s)")
    return int(value)


def time_window(args, info):
    start = to_ticks(args.start, info, "--from") if args.start else None
    end = to_ticks(args.end, info, "--to") if args.end else None
    if start is not None and end is not None and end <= start:
        raise ShotError("--to must be later than --from")
    return start, end


# --------------------------------------------------------------------------- X server and frames

class Display:
    def __init__(self, width, height, tmp):
        n = 99
        while os.path.exists(f"/tmp/.X{n}-lock") or os.path.exists(f"/tmp/.X11-unix/X{n}"):
            n += 1
        self.name = f":{n}"
        # The screen is bigger than the app window, so the pointer can sit outside it and a
        # window that refuses to be as small as asked is still captured whole.
        self.width, self.height = max(width, 2560), height + 200
        self.proc = subprocess.Popen(
            ["Xvfb", self.name, "-screen", "0", f"{self.width}x{self.height}x24",
             "-nolisten", "tcp", "-dpi", "96", "-noreset"],
            stdout=subprocess.DEVNULL, stderr=open(tmp / "xvfb.log", "w"))
        for _ in range(100):
            if subprocess.run(["xdpyinfo", "-display", self.name], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise ShotError("Xvfb did not start; see xvfb.log with --keep")
        subprocess.run(["xdotool", "mousemove", str(self.width - 1), str(self.height - 1)],
                       env={**os.environ, "DISPLAY": self.name}, check=True)

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def grab(display, width, height):
    xwd = subprocess.run(["xwd", "-root", "-silent", "-display", display.name],
                         capture_output=True, check=True).stdout
    ppm = subprocess.run(["convert", "xwd:-", "-crop", f"{width}x{height}+0+0", "+repage",
                          "ppm:-"], input=xwd, capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(ppm)).convert("RGB")


def settle(display, width, height, timeout, need=4, interval=0.3):
    """Grab until `need` frames in a row are identical and not blank."""
    deadline = time.time() + timeout
    last, same = None, 0
    while time.time() < deadline:
        img = grab(display, width, height)
        data = img.tobytes()
        if data == last:
            same += 1
        else:
            last, same = data, 1
        if same >= need and np.ptp(np.asarray(img)) > 0:
            return img
        time.sleep(interval)
    raise ShotError(f"the window was still changing after {timeout:.0f} s")


def geometry(display, wid):
    env = {**os.environ, "DISPLAY": display.name}
    out = subprocess.run(["xdotool", "getwindowgeometry", "--shell", wid],
                         capture_output=True, text=True, env=env, check=True).stdout
    g = dict(line.split("=", 1) for line in out.split())
    return int(g["X"]), int(g["Y"]), int(g["WIDTH"]), int(g["HEIGHT"])


def find_window(display, pid, timeout):
    """The viewer's main window: the biggest visible window the process owns."""
    env = {**os.environ, "DISPLAY": display.name}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(pid)],
                           capture_output=True, text=True, env=env)
        wids = r.stdout.split()
        if wids:
            return max(wids, key=lambda w: geometry(display, w)[2] * geometry(display, w)[3])
        time.sleep(0.2)
    raise ShotError("the viewer never opened a window")


def capture_window(display, wid, width, height, args):
    """Wait for the window to be still at 0,0, and grab it.

    The viewers open at the size they are told to (Surfer's config, GTKWave's [size]). A
    viewer can still open bigger than asked, when the size is below its minimum, or grow
    after it first maps. Forcing it smaller would cut off part of its layout, so the window
    is grabbed at whatever size it settles at, with a warning if that is not the size asked.
    """
    env = {**os.environ, "DISPLAY": display.name}
    if geometry(display, wid)[:2] != (0, 0):
        subprocess.run(["xdotool", "windowmove", wid, "0", "0"], env=env, check=True)
    time.sleep(args.settle)
    for _ in range(3):
        x, y, w, h = geometry(display, wid)
        if (x, y) != (0, 0):
            raise ShotError(f"the window is at {x},{y}, not at 0,0")
        img = settle(display, w, h, args.timeout)
        if geometry(display, wid) == (0, 0, w, h):
            break
    else:
        raise ShotError("the window kept changing size")
    if (w, h) != (width, height):
        say(f"warning: the window is {w}x{h}, not {width}x{height}; the viewer would not "
            f"take that size, so the PNG is {w} px wide")
    return img


# --------------------------------------------------------------------------- cropping

def last_trace_row(img, x0, x1):
    """Lowest row of the block of traces that starts at the top of the window.

    Counts drawn pixels per row in the wave area: pixels far from the area's background
    colour, which is its most common colour. Surfer's alternate row shading and the faint
    fill under a high signal stay below INK, so only lines and text count. Vertical grid and
    tick lines add the same small count to every row, so the threshold sits above the quiet
    rows' level. The scan stops at the first run of GAP_ROWS quiet rows, so the overview and
    status bars at the bottom of the window are never counted as traces.
    """
    a = np.asarray(img)[:, x0:x1].astype(np.int32)
    packed = (a[..., 0] << 16) | (a[..., 1] << 8) | a[..., 2]
    bg = np.bincount(packed.ravel()).argmax()
    bg = np.array([bg >> 16, (bg >> 8) & 255, bg & 255])
    ink = (np.abs(a - bg).max(axis=2) >= INK).sum(axis=1)
    threshold = np.percentile(ink, 10) + max(6, 0.01 * (x1 - x0))
    rows = np.nonzero(ink > threshold)[0]
    if rows.size == 0:
        return None
    last = rows[0]
    for y in rows[1:]:
        if y - last > GAP_ROWS:
            break
        last = y
    return int(last)


def crop(img, spec, pad, wave_x0, wave_x1):
    width, height = img.size
    if spec == "none":
        return img
    if spec != "auto":
        m = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", spec)
        if not m:
            raise ShotError(f"--crop {spec!r}: use auto, none or WxH+X+Y")
        w, h, x, y = map(int, m.groups())
        return img.crop((x, y, min(width, x + w), min(height, y + h)))
    last = last_trace_row(img, wave_x0, wave_x1)
    if last is None:
        raise ShotError("found no traces in the wave area; are the signals empty?")
    bottom = min(height, last + 1 + pad)
    if bottom > height - 60:
        say(f"warning: the traces reach the bottom of the {height}-px window; "
            "raise --height to show them all")
    return img.crop((0, 0, width, bottom))


def write_png(img, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")   # Pillow adds no time or text chunks
    out.write_bytes(buf.getvalue())
    digest = hashlib.sha256(buf.getvalue()).hexdigest()[:16]
    say(f"wrote {out} ({img.size[0]}x{img.size[1]}, sha256 {digest}...)")


# --------------------------------------------------------------------------- viewers

def child_env(display, tmp):
    env = dict(os.environ)
    for d in ("home", "config", "data", "cache", "runtime"):
        (tmp / d).mkdir(mode=0o700, exist_ok=True)
    env.update(DISPLAY=display.name, HOME=str(tmp / "home"), XDG_CONFIG_HOME=str(tmp / "config"),
               XDG_DATA_HOME=str(tmp / "data"), XDG_CACHE_HOME=str(tmp / "cache"),
               XDG_RUNTIME_DIR=str(tmp / "runtime"), NO_AT_BRIDGE="1", GDK_BACKEND="x11",
               LANG="C.UTF-8", LC_ALL="C.UTF-8", TZ="UTC")
    env.pop("WAYLAND_DISPLAY", None)
    return env


def stop(proc):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def log_tail(path, n=15):
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", l) for l in lines]
    keep = [l for l in lines if re.search(r"WARN|ERROR|rror|panick", l)] or lines
    return "\n".join(keep[-n:])


class Wcp:
    """The client side of Surfer's Waveform Control Protocol: JSON messages ending in NUL."""

    def __init__(self, conn):
        self.conn, self.buf = conn, b""

    def send(self, msg):
        self.conn.sendall(json.dumps(msg).encode() + b"\0")

    def recv(self, timeout):
        deadline = time.time() + timeout
        while b"\0" not in self.buf:
            left = deadline - time.time()
            if left <= 0:
                raise ShotError("Surfer stopped answering on WCP")
            self.conn.settimeout(left)
            try:
                data = self.conn.recv(65536)
            except socket.timeout:
                continue
            if not data:
                raise ShotError("Surfer closed the WCP connection")
            self.buf += data
        msg, self.buf = self.buf.split(b"\0", 1)
        return json.loads(msg)

    def command(self, name, **fields):
        self.send({"type": "command", "command": name, **fields})
        while True:
            reply = self.recv(30)
            if reply.get("type") != "event":
                return reply


def surfer_state_with_unit(args, info, cmd_lines, tmp, display, env, run_dir):
    """Run Surfer once to save its state after the command file, then set the time unit.

    Surfer has no command for the ruler's time unit; it lives in the state file as
    wanted_timeunit. Returns the patched state file and the number of items in it.
    """
    state = tmp / "state.surf.ron"
    cmdfile = tmp / "save-state.sucl"
    cmdfile.write_text("\n".join(cmd_lines + [f"save_state_as {state}"]) + "\n")
    logf = open(tmp / "surfer-state.log", "w")
    proc = subprocess.Popen(["surfer", "-c", str(cmdfile), str(info.path)], cwd=run_dir,
                            env=env, stdout=logf, stderr=logf)
    try:
        deadline = time.time() + args.timeout
        size = -1
        while True:
            if state.exists() and state.stat().st_size == size and size > 0:
                break
            size = state.stat().st_size if state.exists() else -1
            if proc.poll() is not None or time.time() > deadline:
                raise ShotError("Surfer did not save its state:\n"
                                + log_tail(tmp / "surfer-state.log"))
            time.sleep(0.3)
    finally:
        stop(proc)
        logf.close()
    text, n = re.subn(r"wanted_timeunit: \w+",
                      f"wanted_timeunit: {SURFER_TIME_UNITS[args.time_unit]}",
                      state.read_text())
    if n != 1:
        raise ShotError("Surfer's state file has no wanted_timeunit; --time-unit needs "
                        "a Surfer that stores it there (0.7.0 does)")
    state.write_text(text)
    return state, text.count("item_ref:")


def run_surfer(args, info, signals, window, tmp, display):
    width, height = args.width or SURFER_WIDTH, args.height
    env = child_env(display, tmp)
    (tmp / "config" / "surfer").mkdir(parents=True, exist_ok=True)
    (tmp / "config" / "surfer" / "config.toml").write_text(SURFER_CONFIG.format(
        width=width, height=height,
        theme=f'theme = "{args.theme}"\n' if args.theme else "",
        layout="show_hierarchy = false\n" if args.hide_side_panel else ""))
    run_dir = tmp / "run"            # no .surfer/ folder here, so no project config is read
    run_dir.mkdir(exist_ok=True)

    lines = []
    if args.command_file:
        lines += Path(args.command_file).read_text().splitlines()
    lines += [f"variable_add {s}" for s in signals]
    if args.time_unit:
        state, expected = surfer_state_with_unit(args, info, lines, tmp, display, env, run_dir)
        surfer_args = ["-s", str(state), str(info.path)]   # -s alone loads no waveform
    else:
        cmdfile = tmp / "view.sucl"
        cmdfile.write_text("\n".join(lines) + "\n")
        surfer_args = ["-c", str(cmdfile), str(info.path)]
        expected = len(signals) if not args.command_file else None

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server.settimeout(args.timeout)
    port = server.getsockname()[1]
    logf = open(tmp / "surfer.log", "w")
    proc = subprocess.Popen(["surfer", "--wcp-initiate", str(port)] + surfer_args,
                            cwd=run_dir, env=env, stdout=logf, stderr=logf)
    try:
        try:
            conn, _ = server.accept()
        except socket.timeout:
            raise ShotError("Surfer never connected over WCP:\n" + log_tail(tmp / "surfer.log"))
        wcp = Wcp(conn)
        wcp.send({"type": "greeting", "version": "0", "commands": []})
        greeting = wcp.recv(args.timeout)
        if "set_viewport_range_to" not in greeting.get("commands", []) and window != (None, None):
            say("warning: this Surfer does not advertise set_viewport_range")

        # Wait until the signals are on screen. With a command file of unknown length, wait
        # until the list has stopped growing for 1.5 s.
        deadline = time.time() + args.timeout
        prev, since = None, time.time()
        while True:
            reply = wcp.command("get_item_list")
            ids = reply.get("ids", []) if reply.get("type") == "response" else []
            if expected and len(ids) >= expected:
                break
            if not expected and ids:
                if ids != prev:
                    prev, since = ids, time.time()
                elif time.time() - since >= 1.5:
                    break
            if proc.poll() is not None:
                raise ShotError("Surfer exited:\n" + log_tail(tmp / "surfer.log"))
            if time.time() > deadline:
                raise ShotError("Surfer shows no signals. Check the names in the command "
                                "file:\n" + log_tail(tmp / "surfer.log"))
            time.sleep(0.25)

        start, end = window
        if start is not None or end is not None:
            start = info.start if start is None else start
            end = info.end if end is None else end
            reply = wcp.command("set_viewport_range", start=start, end=end)
            if reply.get("type") != "response":
                raise ShotError(f"Surfer refused the time window: {reply}")

        wid = find_window(display, proc.pid, args.timeout)
        img = capture_window(display, wid, width, height, args)
    finally:
        stop(proc)
        server.close()
        logf.close()
    for line in log_tail(tmp / "surfer.log", 50).splitlines():
        if "ERROR" in line or "theme" in line.lower():
            say("surfer: " + line.strip())
    # The wave canvas always covers the right-hand part of Surfer's window.
    return img, int(0.65 * img.size[0]), int(0.98 * img.size[0])


def gtkwave_zoom(start, end, pane):
    """The save-file zoom that puts start on the pane's first column and end on its last.

    GTKWave's zoom z shows 2**-z time units per 200 pixels (currenttime.c).
    """
    return -math.log2(200.0 * (end - start) / (pane - 1))


def longest_run(mask, max_gap=2):
    """(start, end) of the longest run of True in mask, bridging gaps of up to max_gap."""
    xs = np.flatnonzero(mask)
    if xs.size == 0:
        return 0, 0
    breaks = np.flatnonzero(np.diff(xs) > max_gap + 1)
    starts = np.concatenate(([xs[0]], xs[breaks + 1]))
    ends = np.concatenate((xs[breaks], [xs[-1]])) + 1
    i = int(np.argmax(ends - starts))
    return int(starts[i]), int(ends[i])


def wave_pane(img):
    """Left and right x (end exclusive) of GTKWave's black wave pane.

    Looks along rows in the lower half of the window, where there are usually no traces.
    The pane is black with a dark blue 1-px border; the widgets around it are light grey.
    Anything bright inside it (a 1-px grid line) is bridged. The most common answer wins.
    """
    a = np.asarray(img)
    height = a.shape[0]
    votes = {}
    for y in range(int(height * 0.45), int(height * 0.92), 5):
        run = longest_run(a[y].max(axis=1) < 128)
        if run[1] - run[0] > 50:
            votes[run] = votes.get(run, 0) + 1
    if not votes:
        raise ShotError("could not find GTKWave's wave pane")
    return max(votes, key=votes.get)


def gtkw_text(args, info, signals, start, zoom, width, height):
    out = [f'[dumpfile] "{info.path}"', f"[timestart] {start}", f"[size] {width} {height}",
           "[pos] 0 0", f"*{zoom:.6f} -1"]
    if args.save:
        for line in Path(args.save).read_text().splitlines():
            if re.match(r"\[(dumpfile|dumpfile_mtime|dumpfile_size|savefile|timestart|size|pos"
                        r"|pattern_trace)\]", line) or line.startswith("*"):
                continue
            out.append(line)
    else:
        out += ["[sst_width] 200", "[signals_width] 150", "[sst_expanded] 1",
                "[sst_vpaned_height] 150"]
    for s in signals:
        w, rng = info.vars[s]
        out += ["@22" if w > 1 else "@28", s + rng]
    return "\n".join(out) + "\n"


def run_gtkwave(args, info, signals, window, tmp, display):
    width, height = args.width or GTKWAVE_WIDTH, args.height
    env = child_env(display, tmp)
    rc = tmp / "gtkwaverc"
    rc.write_text(GTKWAVE_RC)
    start, end = window
    start = info.start if start is None else start
    end = info.end if end is None else end
    if start is None or end is None or end <= start:
        raise ShotError("cannot tell the file's time span; give --from and --to")

    pane = width - 442          # the default layout's pane width; measured and corrected below
    for attempt in range(2):
        zoom = gtkwave_zoom(start, end, pane)
        save = tmp / f"view{attempt}.gtkw"
        save.write_text(gtkw_text(args, info, signals, start, zoom, width, height))
        run_dir = tmp / f"run{attempt}"
        run_dir.mkdir(exist_ok=True)
        logf = open(tmp / f"gtkwave{attempt}.log", "w")
        proc = subprocess.Popen(["gtkwave", "-r", str(rc), str(info.path), str(save)],
                                cwd=run_dir, env=env, stdout=logf, stderr=logf)
        try:
            wid = find_window(display, proc.pid, args.timeout)
            img = capture_window(display, wid, width, height, args)
        finally:
            stop(proc)
            logf.close()
        x0, x1 = wave_pane(img)
        if x1 - x0 == pane:
            break
        pane = x1 - x0
    else:
        say("warning: GTKWave's wave pane changed width between runs; the time window "
            "may be off by a few pixels")
    return img, x0 + 2, x1 - 2


# --------------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Render a PNG of Surfer or GTKWave showing a waveform, headless.")
    sub = p.add_subparsers(dest="viewer", required=True)
    for name in ("surfer", "gtkwave"):
        s = sub.add_parser(name, help=f"screenshot {name}")
        s.add_argument("wave", type=Path, help="the FST or VCD file")
        s.add_argument("-o", "--out", type=Path, help="the PNG to write")
        s.add_argument("-s", "--signals", action="append", default=[], metavar="NAMES",
                       help="signals to show, comma- or space-separated, top to bottom")
        s.add_argument("--from", dest="start", metavar="TIME",
                       help="left edge of the time window, e.g. 120ns, or a tick count")
        s.add_argument("--to", dest="end", metavar="TIME", help="right edge of the time window")
        s.add_argument("--width", type=int,
                       help=f"window width in px (default {SURFER_WIDTH if name == 'surfer' else GTKWAVE_WIDTH})")
        s.add_argument("--height", type=int, default=WINDOW_HEIGHT,
                       help=f"window height in px before trimming (default {WINDOW_HEIGHT})")
        s.add_argument("--crop", default="auto",
                       help="auto (trim below the last trace), none, or WxH+X+Y")
        s.add_argument("--pad", type=int,
                       help=f"px kept under the last trace with --crop auto "
                            f"(default {SURFER_PAD if name == 'surfer' else GTKWAVE_PAD})")
        s.add_argument("--settle", type=float, default=1.0,
                       help="seconds to wait before checking the window is still")
        s.add_argument("--timeout", type=float, default=90.0, help="give up after this long")
        s.add_argument("--list", action="store_true",
                       help="print every signal name in the file and exit")
        s.add_argument("--keep", type=Path, metavar="DIR",
                       help="use DIR as the scratch folder and keep it: logs, the generated "
                            "command or save file, and full.png, the uncropped frame")
        if name == "surfer":
            s.add_argument("-c", "--command-file", type=Path,
                           help="a Surfer command file, as in `surfer -c view.sf`")
            s.add_argument("--theme", help="a Surfer theme name (default: Surfer's own)")
            s.add_argument("--time-unit", choices=sorted(SURFER_TIME_UNITS),
                           help="unit for the time ruler (default: the file's own, as "
                                "Surfer opens it)")
            s.add_argument("--hide-side-panel", action="store_true",
                           help="hide the Scopes and Variables panel")
        else:
            s.add_argument("-a", "--save", type=Path,
                           help="a .gtkw save file whose signal list to use")
    args = p.parse_args(argv)

    try:
        info = read_wave_info(args.wave)
        if args.list:
            for v in sorted(info.vars):
                w, rng = info.vars[v]
                print(f"{v}{rng}" if rng else v)
            return 0
        if not args.out:
            raise ShotError("give the PNG to write with -o")
        if args.out.suffix.lower() != ".png":
            raise ShotError("-o must end in .png")
        names = [n for item in args.signals for n in re.split(r"[,\s]+", item) if n]
        signals = resolve_signals(names, info)
        if not signals and not getattr(args, "command_file", None) and \
                not getattr(args, "save", None):
            raise ShotError("say what to show: --signals, or -c (Surfer) / -a (GTKWave)")
        for f in (getattr(args, "command_file", None), getattr(args, "save", None)):
            if f and not f.is_file():
                raise ShotError(f"{f}: no such file")
        window = time_window(args, info)
        args.height = max(200, args.height)
        pad = args.pad if args.pad is not None else (
            SURFER_PAD if args.viewer == "surfer" else GTKWAVE_PAD)
        args.wave = args.wave.resolve()
        info.path = args.wave
        if getattr(args, "command_file", None):
            args.command_file = args.command_file.resolve()

        if args.keep:
            tmp = args.keep.resolve()
            tmp.mkdir(parents=True, exist_ok=True)
        else:
            tmp = Path(tempfile.mkdtemp(prefix="waveshot-"))
        try:
            display = Display(args.width or (SURFER_WIDTH if args.viewer == "surfer"
                                             else GTKWAVE_WIDTH), args.height, tmp)
            try:
                run = run_surfer if args.viewer == "surfer" else run_gtkwave
                img, x0, x1 = run(args, info, signals, window, tmp, display)
            finally:
                display.close()
            if args.keep:
                img.save(tmp / "full.png")
            write_png(crop(img, args.crop, pad, x0, x1), args.out)
        finally:
            if args.keep:
                say(f"scratch files kept in {tmp}")
            else:
                shutil.rmtree(tmp, ignore_errors=True)
        return 0
    except ShotError as e:
        say(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
