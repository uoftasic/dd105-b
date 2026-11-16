"""
DD105 -- the bug catalogue.

Fifteen one-line edits to the router in `rtl/`. Each one makes a router that
is wrong in a specific, findable way, and all fifteen pass the router's shipped
test, `smoke/tb_smoke.sv`. That test reads the ID register, sets up one route,
sends three short packets down it and checks that they come out. It passes on
a router whose interrupt ignores its enables, whose output changes while it is
stalled, and which forgets to drop packets for a disabled route.

Each entry names one line of one file in `rtl/` (`anchor`, the exact text of
the whole line), the expression in that line that the bug changes (`golden`,
which must appear in the line exactly once) and what it becomes (`buggy`).
The broken line is the anchor with `golden` replaced by `buggy`.

`inject.py` turns the catalogue into a design. `inject.py --all` writes one
"faulty" copy of the RTL in which every anchored expression becomes

    (router_bug_pkg::bug_id == N ? (buggy) : (golden))

so that one build holds the golden router and all fifteen broken ones, and
`+BUG=B07` on the simulator's command line picks one at time 0. Before it
writes anything, inject.py checks that every anchor still matches exactly one
line and every `golden` expression appears exactly once in it. If somebody
edits `rtl/` and an anchor drifts, it refuses, rather than producing a
"broken" router that is actually fine: a grader that says PASS when it
checked nothing is worse than no grader.

`caught_by` lists the checks in the directed reference test
(`solutions/tb_directed.sv`) that fail on that bug. It is copied from a run,
not written by hand; `solutions/README.md` has the counts.

You are not meant to read the anchors before you have hunted for the bug.
`python3 bugs.py` prints the ids, tiers and what each bug hides behind and
teaches, and nothing about where it is. Reading the rest of this file costs
you the lab.
"""

TIER_NAMES = {
    1: "registers",
    2: "routing",
    3: "buffer corners",
    4: "protocol",
    5: "backpressure",
    6: "reset",
}

BUGS = {

    # -- Tier 1: registers -------------------------------------------------

    "B01": dict(
        name="status_write_clears_all",
        tier=1, region="router_regs.sv, STATUS",
        summary="any write to STATUS clears every bit, not just the bits written as 1",
        hides_behind="clearing every STATUS bit at once",
        teaches="write-1-to-clear is per bit: clear one bit and check that the others survive",
        file="router_regs.sv",
        anchor="    else if (wr_status) status_q <= (status_q & ~pwdata[NUM_EV-1:0]) | ev;",
        golden="(status_q & ~pwdata[NUM_EV-1:0]) | ev",
        buggy="ev",
        caught_by=["C08", "C15"],
    ),

    "B02": dict(
        name="irq_ignores_int_en",
        tier=1, region="router_regs.sv, interrupt",
        summary="irq is the OR of STATUS alone; INT_EN has no effect",
        hides_behind="turning on every interrupt enable before looking at irq",
        teaches="an enable is a mask, and a mask has to be tested off as well as on",
        file="router_regs.sv",
        anchor="  assign irq = |(status_q & int_en_q);",
        golden="|(status_q & int_en_q)",
        buggy="|status_q",
        caught_by=["C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C14", "C15", "C17"],
    ),

    "B03": dict(
        name="route3_readback_swapped",
        tier=1, region="router_regs.sv, read data",
        summary="ROUTE3 reads back with EN and PORT swapped; the route itself works",
        hides_behind="setting up the routing table without reading it back",
        teaches="read back what you write, with values whose bits differ, in every register",
        file="router_regs.sv",
        anchor="      W_ROUTE3:   rdata[1:0]            = {route_port_q[3], route_en_q[3]};",
        golden="{route_port_q[3], route_en_q[3]}",
        buggy="{route_en_q[3], route_port_q[3]}",
        caught_by=["C02"],
    ),

    "B04": dict(
        name="misaligned_address_accepted",
        tier=1, region="router_regs.sv, address decode",
        summary="an address that isn't a multiple of 4 gets no PSLVERR and reaches the register below it",
        hides_behind="using only the addresses in the register map",
        teaches="a bus has a negative half: every address outside the map must fail, misaligned ones too",
        file="router_regs.sv",
        anchor="  assign bad_addr = !hit || (paddr[1:0] != 2'b00);",
        golden="!hit || (paddr[1:0] != 2'b00)",
        buggy="!hit",
        caught_by=["C03"],
    ),

    # -- Tier 2: routing ---------------------------------------------------

    "B05": dict(
        name="dst_field_off_by_one",
        tier=2, region="router_ingress.sv, route lookup",
        summary="the route is looked up with header bits 6:5 instead of 7:6",
        hides_behind="sending to DST 0 only, or setting every route the same way",
        teaches="test a field by giving each of its bits its own effect",
        file="router_ingress.sv",
        anchor="  assign dst       = in_data[7:6];",
        golden="in_data[7:6]",
        buggy="in_data[6:5]",
        caught_by=["C04", "C05", "C06", "C08", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18"],
    ),

    "B06": dict(
        name="disabled_route_forwards",
        tier=2, region="router_ingress.sv, admission",
        summary="a packet for a disabled route is forwarded anyway (and still counted as a drop)",
        hides_behind="never disabling a route",
        teaches="negative tests: only a test that disables a route can see what happens to it",
        file="router_ingress.sv",
        anchor="  assign admit     = lkp_en && room;",
        golden="lkp_en && room",
        buggy="room",
        caught_by=["C05", "C06", "C07", "C08", "C09", "C12", "C17"],
    ),

    "B07": dict(
        name="full_counted_on_disabled_route",
        tier=2, region="router_ingress.sv, drop events",
        summary="a packet for a disabled route whose output is too full counts as both NOROUTE and FULL",
        hides_behind="testing each drop reason on its own",
        teaches="two conditions at once is a cross, and cross coverage is how you know you tried it",
        file="router_ingress.sv",
        anchor="  assign ev_full     = hs && at_head && lkp_en && !room;",
        golden="hs && at_head && lkp_en && !room",
        buggy="hs && at_head && !room",
        caught_by=["C11"],
    ),

    # -- Tier 3: buffer corners --------------------------------------------

    "B08": dict(
        name="admission_off_by_one",
        tier=3, region="router_ingress.sv, admission",
        summary="a packet is dropped when its output holds exactly 8 beats, which still has room",
        hides_behind="keeping the outputs drained, or flooding them, and never stopping at exactly 8",
        teaches="a threshold is tested at the threshold, not near it",
        file="router_ingress.sv",
        anchor="  assign room      = (lkp_level <= LEVEL_W'(ADMIT_MAX));",
        golden="(lkp_level <= LEVEL_W'(ADMIT_MAX))",
        buggy="(lkp_level < LEVEL_W'(ADMIT_MAX))",
        caught_by=["C06", "C08", "C10", "C11", "C14", "C15"],
    ),

    "B09": dict(
        name="write_pointer_power_of_two",
        tier=3, region="router_fifo.sv, write pointer",
        summary="the write pointer wraps at 16, as if the 15-entry RAM were a power of two",
        hides_behind="short tests: fewer than 16 beats through one output",
        teaches="run enough traffic to wrap every pointer, more than once",
        file="router_fifo.sv",
        anchor="      if (push) wr_ptr_q <= (wr_ptr_q == PTR_LAST) ? '0 : wr_ptr_q + 1'b1;",
        golden="(wr_ptr_q == PTR_LAST) ? '0 : wr_ptr_q + 1'b1",
        buggy="wr_ptr_q + 1'b1",
        caught_by=["C04", "C05", "C10", "C12", "C13", "C14", "C15"],
    ),

    # -- Tier 4: protocol --------------------------------------------------

    "B10": dict(
        name="output_reloads_while_stalled",
        tier=4, region="router_fifo.sv, output register",
        summary="the output register loads the next beat even while the sink holds out_ready low",
        hides_behind="a sink that is always ready",
        teaches="valid/ready stability is a rule you write as an assertion and test with stalls",
        file="router_fifo.sv",
        anchor="  assign load = (count_q != '0) && (!ovalid_q || out_ready);",
        golden="(count_q != '0) && (!ovalid_q || out_ready)",
        buggy="(count_q != '0)",
        caught_by=["C06", "C08", "C10", "C11", "C14", "C15", "C18"],
    ),

    "B11": dict(
        name="cut_packet_has_no_last",
        tier=4, region="router_ingress.sv, length limit",
        summary="a packet cut at 8 beats goes out without out_last, so it runs into the next packet",
        hides_behind="sending only legal packets of 8 beats or fewer",
        teaches="the error path is part of the design, and it needs stimulus of its own",
        file="router_ingress.sv",
        anchor="  assign wr_last  = in_last || at_max;   // the 8th beat always ends the packet",
        golden="in_last || at_max",
        buggy="in_last",
        caught_by=["C08", "C09", "C12"],
    ),

    # -- Tier 5: backpressure ----------------------------------------------

    "B12": dict(
        name="out1_uses_out0_ready",
        tier=5, region="router.sv, buffer 1 hookup",
        summary="output 1 moves on out0_ready instead of out1_ready",
        hides_behind="driving both out_ready signals the same way",
        teaches="independent outputs have to be tested with outputs that disagree",
        file="router.sv",
        anchor="    .out_ready (out1_ready),",
        golden="out1_ready",
        buggy="out0_ready",
        caught_by=["C10", "C14", "C15"],
    ),

    "B13": dict(
        name="admission_checks_other_output",
        tier=5, region="router_ingress.sv, admission",
        summary="room is judged from the level of the other output",
        hides_behind="stalling both outputs together, or never letting one fill",
        teaches="a scoreboard that predicts drops has to model each output's level on its own",
        file="router_ingress.sv",
        anchor="  assign lkp_level = lkp_port ? level1 : level0;",
        golden="lkp_port ? level1 : level0",
        buggy="lkp_port ? level0 : level1",
        caught_by=["C06", "C08", "C10", "C11", "C14", "C15"],
    ),

    # -- Tier 6: reset -----------------------------------------------------

    "B14": dict(
        name="enable_resets_to_one",
        tier=6, region="router_regs.sv, CTRL",
        summary="CTRL.EN resets to 1, so the router takes packets before it is configured",
        hides_behind="configuring every register before sending anything",
        teaches="reset values are part of the spec, and only a test that reads them checks them",
        file="router_regs.sv",
        anchor="      en_q          <= 1'b0;",
        golden="1'b0",
        buggy="1'b1",
        caught_by=["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19"],
    ),

    "B15": dict(
        name="output_valid_survives_reset",
        tier=6, region="router_fifo.sv, reset",
        summary="reset doesn't clear the output register, so a stalled beat comes out after reset",
        hides_behind="resetting only at time 0, when every buffer is already empty",
        teaches="reset with traffic in flight; a reset at time 0 proves very little",
        file="router_fifo.sv",
        anchor="      ovalid_q <= 1'b0;",
        golden="1'b0",
        buggy="ovalid_q",
        caught_by=["C18"],
    ),
}


def ids():
    """Bug ids in tier order, then id order."""
    return sorted(BUGS, key=lambda k: (BUGS[k]["tier"], k))


def number(bug_id):
    """B07 -> 7, the value of router_bug_pkg::bug_id that selects it."""
    return int(bug_id[1:])


def resolve(name):
    """Accept 'B07', 'b07', 'B7', '7' or the bug's name. Raise a useful error."""
    key = name.strip()
    if key.upper() in BUGS:
        return key.upper()
    digits = key[1:] if key[:1] in "bB" else key
    if digits.isdigit() and f"B{int(digits):02d}" in BUGS:
        return f"B{int(digits):02d}"
    for k, b in BUGS.items():
        if b["name"] == key:
            return k
    raise KeyError(f"no bug named {name!r}. Known bugs: {', '.join(ids())}")


def buggy_line(bug_id):
    """The anchored line as it reads with the bug in it."""
    b = BUGS[bug_id]
    return b["anchor"].replace(b["golden"], b["buggy"], 1)


if __name__ == "__main__":
    print(f"DD105 bug catalogue: {len(BUGS)} one-line bugs, all of which pass smoke/tb_smoke.sv\n")
    for tier in sorted(TIER_NAMES):
        print(f"  Tier {tier}: {TIER_NAMES[tier]}")
        for k in ids():
            if BUGS[k]["tier"] != tier:
                continue
            print(f"    {k}")
            print(f"        hides behind : {BUGS[k]['hides_behind']}")
            print(f"        teaches      : {BUGS[k]['teaches']}")
        print()
