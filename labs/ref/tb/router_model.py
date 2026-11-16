"""
DD105-B reference environment: a cycle-exact model of the router, written
from docs/reference/router-spec.md alone. Plain Python, with no cocotb or
pyuvm in it, so it can be run and tested outside the simulator.

The scoreboard calls step() once per cycle with what the cycle monitor read
at that cycle's falling edge, where every input and output holds its value
for the cycle. step() first predicts every output the router drives in that
cycle from the model's state (and, for pready and pslverr, from the APB
inputs in the same cycle), and returns the predictions; then it applies the
rising edge that ends the cycle, using the cycle's inputs.

Cycle n is the clock period that ends at rising edge n. The model follows its
own predictions: a beat moves on the input when in_valid is 1 and the
model's in_ready is 1, and on an output when the model's out_valid is 1 and
the sampled out_ready is 1. So after the first difference the model and the
design go their separate ways, and the scoreboard stops after a few dozen.
"""

from collections import deque

# Register word numbers (address >> 2) and the ID value.
ID, CTRL, STATUS, INT_EN, DROP_CNT, LEVEL = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
ROUTE = (0x08, 0x09, 0x0A, 0x0B)
NAMES = {ID: "ID", CTRL: "CTRL", STATUS: "STATUS", INT_EN: "INT_EN", DROP_CNT: "DROP_CNT",
         LEVEL: "LEVEL", 0x08: "ROUTE0", 0x09: "ROUTE1", 0x0A: "ROUTE2", 0x0B: "ROUTE3"}
ID_VALUE = 0xD105_0001
EV_NOROUTE, EV_FULL, EV_OVERSIZE = 1, 2, 4
MAX_LEN = 8
ADMIT_MAX = 8          # admitted at a level of 8 or less
DEPTH = 16

HEAD, FWD, DROP, TAIL = "HEAD", "FWD", "DROP", "TAIL"


def bad_addr(paddr):
    """Not a multiple of 4, or not in the register map."""
    return (paddr & 3) != 0 or (paddr >> 2) not in NAMES


def reg_name(paddr):
    return NAMES.get(paddr >> 2, f"{paddr:02x}") if not (paddr & 3) else f"{paddr:02x}"


class Sample:
    """Every pin of the router in one cycle, as the cycle monitor read it."""
    PINS = ("rst_n", "psel", "penable", "pwrite", "paddr", "pwdata", "prdata", "pready", "pslverr",
            "irq", "in_valid", "in_ready", "in_data", "in_last",
            "out0_valid", "out0_ready", "out0_data", "out0_last",
            "out1_valid", "out1_ready", "out1_data", "out1_last")

    def __init__(self, cycle=0, **pins):
        self.cycle = cycle
        for p in self.PINS:
            setattr(self, p, pins.get(p, 0))


class Packet:
    """What the model decided for one packet, for the scoreboard's counts and coverage."""

    def __init__(self, cycle, dst, port, level, fate):
        self.cycle, self.dst, self.port, self.level, self.fate = cycle, dst, port, level, fate
        self.beats = 0
        self.oversize = False


class RouterModel:
    def __init__(self):
        self.started = False          # nothing is predicted before the first reset
        self.reset()
        self.started = False
        self.packets = []             # finished packets, for coverage; the scoreboard drains it
        self.current = None
        self.on_packet = None         # called with each Packet when its last beat is accepted

    # ── state ────────────────────────────────────────────────────────────────
    def reset(self):
        self.en = 0
        self.int_en = 0
        self.status = 0
        self.cnt_noroute = 0
        self.cnt_full = 0
        self.route_en = [0, 0, 0, 0]
        self.route_port = [0, 0, 0, 0]
        self.state = HEAD
        self.beats = 0
        self.port = 0
        self.q = (deque(), deque())   # each output: (data, last, cycle written), oldest first
        self.rd_wait = False          # between the first and second access cycle of a read
        self.prdata = 0
        self.current = None
        self.started = True

    def level(self, port):
        return len(self.q[port])

    def read_value(self, paddr):
        """What a read whose first access cycle is now returns: (good, value)."""
        if bad_addr(paddr):
            return False, 0
        w = paddr >> 2
        if w == ID:
            return True, ID_VALUE
        if w == CTRL:
            return True, self.en
        if w == STATUS:
            return True, self.status
        if w == INT_EN:
            return True, self.int_en
        if w == DROP_CNT:
            return True, (self.cnt_full << 8) | self.cnt_noroute
        if w == LEVEL:
            return True, (self.level(1) << 8) | self.level(0)
        n = ROUTE.index(w)
        return True, (self.route_port[n] << 1) | self.route_en[n]

    # ── one cycle ────────────────────────────────────────────────────────────
    def predict(self, s):
        """The router's outputs in the cycle of sample s, from the state at its start."""
        if not s.rst_n:
            return dict(in_ready=0, out0_valid=0, out1_valid=0, irq=0, pready=1, pslverr=0, prdata=0)
        p = {}
        p["in_ready"] = 1 if (self.state != HEAD or self.en) else 0
        for k in (0, 1):
            q = self.q[k]
            valid = bool(q) and q[0][2] + 2 <= s.cycle
            p[f"out{k}_valid"] = int(valid)
            if valid:
                p[f"out{k}_data"], p[f"out{k}_last"] = q[0][0], q[0][1]
        p["irq"] = 1 if (self.status & self.int_en) else 0
        access = s.psel and s.penable
        p["pready"] = 0 if (access and not s.pwrite and not self.rd_wait) else 1
        p["pslverr"] = 1 if (access and p["pready"] and bad_addr(s.paddr)) else 0
        p["prdata"] = self.prdata
        return p

    def step(self, s):
        """Predict cycle s, then apply the rising edge that ends it. Returns the
        predictions, or None before the first reset."""
        if not s.rst_n:
            self.reset()              # asynchronous: the whole cycle is in reset
            return self.predict(s)
        if not self.started:
            return None
        p = self.predict(s)
        self._edge(s, p)
        return p

    def _edge(self, s, p):
        ev = 0
        # APB, from the state at the start of the cycle
        write = None
        access = s.psel and s.penable
        if access and not s.pwrite and not self.rd_wait:
            good, value = self.read_value(s.paddr)
            self.prdata = value if good else 0
            self.rd_wait = True
        elif access and p["pready"]:
            if s.pwrite and not bad_addr(s.paddr):
                write = (s.paddr >> 2, s.pwdata)
            self.rd_wait = False

        # the input stream, against the routing table and levels as they are now
        if s.in_valid and p["in_ready"]:
            data, last = s.in_data, s.in_last
            if self.state == HEAD:
                dst = data >> 6
                port = self.route_port[dst]
                level = self.level(port)
                if not self.route_en[dst]:
                    ev |= EV_NOROUTE
                    fate, nxt = "noroute", DROP
                elif level > ADMIT_MAX:
                    ev |= EV_FULL
                    fate, nxt = "full", DROP
                else:
                    fate, nxt = f"out{port}", FWD
                    self.port = port
                    self.q[port].append((data, last, s.cycle))
                self.current = Packet(s.cycle, dst, port, level, fate)
                self.beats = 1
                self.state = HEAD if last else nxt
            elif self.state in (FWD, DROP):
                self.beats += 1
                at_max = self.beats == MAX_LEN
                if self.state == FWD:
                    self.q[self.port].append((data, 1 if (last or at_max) else 0, s.cycle))
                if last:
                    self.state = HEAD
                elif at_max:
                    ev |= EV_OVERSIZE
                    self.current.oversize = True
                    self.state = TAIL
            elif self.state == TAIL and last:
                self.state = HEAD
            if self.current is not None:
                self.current.beats += 1
                if last:
                    self.packets.append(self.current)
                    if self.on_packet:
                        self.on_packet(self.current)
                    self.current = None

        # the outputs
        for k in (0, 1):
            if p[f"out{k}_valid"] and getattr(s, f"out{k}_ready"):
                self.q[k].popleft()

        # registers: a write takes effect at this edge; events win over a clear
        clear, clear_cnt = 0, False
        if write:
            w, v = write
            if w == CTRL:
                self.en = v & 1
            elif w == INT_EN:
                self.int_en = v & 7
            elif w == STATUS:
                clear = v & 7
            elif w == DROP_CNT:
                clear_cnt = True
            elif w in ROUTE:
                n = ROUTE.index(w)
                self.route_en[n], self.route_port[n] = v & 1, (v >> 1) & 1
        self.status = (self.status & ~clear & 7) | ev
        if clear_cnt:
            self.cnt_noroute = self.cnt_full = 0
        if ev & EV_NOROUTE:
            self.cnt_noroute = min(self.cnt_noroute + 1, 255)
        if ev & EV_FULL:
            self.cnt_full = min(self.cnt_full + 1, 255)
