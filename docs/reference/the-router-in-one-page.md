# The router in one page

This page answers: *what does the router do, in the detail a test needs, without reading the whole
specification first?*

[The packet router](router-spec.md) is the specification you write every testbench in this course
from, and it describes the router's pins cycle by cycle, which makes it long. This page is the same
design cut down to what your tests depend on: the blocks, the ports, the register map in one table,
and the rules, each with a link to the section of the specification it comes from. When you need a
cycle-by-cycle answer, follow the link. The specification's timing examples, E1 to E9, are printed
by a run of the RTL (`labs/common/smoke/tb_examples.sv`), so they show exactly what the router
does.

## The blocks

![The router's four blocks. Arrows show which way the data goes; each stream also has a `ready`
going the other way.](../assets/img/router-block.svg){width=640 fig-alt="A block diagram. The
input stream in_* enters a box labelled ingress: route, drop, cut. Two arrows, push0 and push1,
leave the ingress for two boxes, buffer 0 and buffer 1, each holding 16 beats, drawn inside a
dashed outline. Buffer 0 drives out0_* and buffer 1 drives out1_*. Below them is a wide box
labelled registers, with a two-way APB arrow on its left and irq leaving on its right. An arrow
labelled CTRL.EN, ROUTE0-3 goes up from the registers to the ingress, and an arrow labelled drops,
oversize goes down from the ingress to the registers. An arrow labelled LEVEL0, LEVEL1 leaves the
dashed outline round the buffers and goes down to the registers, with a branch back up into the
ingress."}

The RTL is 730 lines in five files in
[`labs/common/rtl/`](https://github.com/uoftasic/dd105-a/tree/main/labs/common/rtl): a package of
sizes and register offsets, one file for each of the three kinds of block (the two buffers are two
instances of `router_fifo`), and the top module, `router`, which connects them. You don't need to read them, and in the later labs you'll be testing builds
whose RTL you can't trust anyway, but this is how they divide the work:

- The **ingress** takes packets from the input stream. When a packet's header arrives it looks up
  the routing table and the level of the output the route names, and decides once what happens to
  the whole packet: write it into one output's buffer, or drop it and count it. It also cuts a
  packet that is longer than 8 beats.
- Each **buffer** holds up to 16 beats, 15 in a small RAM and one in the register that drives the
  output pins, so `out0_valid`, `out0_data` and `out0_last` come straight from flip-flops. Its
  **level** is the number of beats it holds, the one on the pins included.
- The **registers** are the APB slave. They hold the configuration (`CTRL.EN` and the four
  `ROUTE` entries), record drops and oversize packets in `STATUS` and `DROP_CNT`, read back both
  levels in `LEVEL`, and drive `irq`.

The sizes are small on purpose, so every corner is a short simulation away: 8-bit beats, 4 routes, 2
outputs, packets of 1 to 8 beats, 16 beats per buffer, and drop counters that stop at 255
([Sizes](router-spec.md#sizes)).

## Ports

Everything happens on the rising edge of `clk`, the APB port included, and the router samples its
inputs there ([Ports](router-spec.md#ports), [Cycles and handshakes](router-spec.md#cycles-and-handshakes)).

| Group | Inputs | Outputs | Notes |
|---|---|---|---|
| Clock and reset | `clk`, `rst_n` | | `rst_n` is active low and asynchronous |
| APB slave | `psel`, `penable`, `pwrite`, `paddr[7:0]`, `pwdata[31:0]` | `prdata[31:0]`, `pready`, `pslverr` | APB3 with one slave select and no `PSTRB`, so a write writes the whole register |
| Interrupt | | `irq` | active high, a level |
| Input stream | `in_valid`, `in_data[7:0]`, `in_last` | `in_ready` | the testbench is the source |
| Output 0 | `out0_ready` | `out0_valid`, `out0_data[7:0]`, `out0_last` | the testbench is the sink |
| Output 1 | `out1_ready` | `out1_valid`, `out1_data[7:0]`, `out1_last` | the same as output 0 |

A **handshake** happens in a cycle where `valid` and `ready` are both 1, and the beat moves at the
rising edge that ends that cycle. The course's testbenches change inputs 1 ns after a rising edge
and sample at the falling edge, so nothing changes at the moment it's sampled.

Verilator has only the values 0 and 1, so a `data` signal whose `valid` is low still holds
whatever it last carried. Never compare `out0_data` or `out0_last` in a cycle where `out0_valid` is
0, because what you'd be comparing is left over from an earlier beat.

## Packets and routing

A packet is 1 to 8 beats on the input stream. Its first beat is the **header**, and the beat with
`in_last` = 1 ends it. The header's bits 7:6 are `DST`, which picks one of the four routing table
entries, `ROUTE0` to `ROUTE3`; bits 5:0 are a tag that the router passes through untouched, and the
course's testbenches put a sequence number there. A delivered packet comes out exactly as it went in
([Packets](router-spec.md#packets)).

The router decides a packet's fate once, in the cycle its header is accepted, from `ROUTE[DST]` and
the level of the output that entry's `PORT` names, both as they are in that cycle
([Routing](router-spec.md#routing)):

| `ROUTE[DST].EN` | Level of output `PORT` | The packet is | Counted in |
|---|---|---|---|
| 0 | anything | dropped | `NOROUTE_CNT`, `STATUS.NOROUTE` |
| 1 | 9 to 16 | dropped | `FULL_CNT`, `STATUS.FULL` |
| 1 | 0 to 8 | written, beat by beat, into output `PORT`'s buffer | |

The decision holds for the whole packet. A write to `ROUTE[DST]` or `CTRL`, or a change in either
level, while a packet is coming in affects only later packets: a header accepted in the cycle after
the write completes uses the new value, and one accepted in the same cycle uses the old one. A
dropped packet is still taken from the input, with `in_ready` at 1 for every beat, so a full output
never holds up packets for the other one.

Keep three consequences of this in mind when you write a scoreboard:

- A packet is admitted at a level of 8 or less and is at most 8 beats long, so an admitted packet
  always fits in 16. With output 0 stalled, two 8-beat packets are admitted (at levels 0 and 8) and
  the third is dropped, and nine 1-beat packets are admitted (at levels 0 to 8) and the tenth is
  dropped.
- The level in the header's cycle counts every beat written into the output in earlier cycles,
  minus every beat taken by an output handshake in earlier cycles. Neither the header itself nor a
  handshake on the output in the same cycle counts. Because you see both kinds of beat on the pins,
  a testbench can track both levels exactly and predict every FULL drop.
- A packet for a disabled route is NOROUTE whatever the level of the output its `PORT` names, and
  it's never counted as FULL as well.

A drop adds one to its counter, unless the counter is already 255, and sets its `STATUS` bit, both
at the edge that ends the header's cycle ([Dropped packets](router-spec.md#dropped-packets)).

A packet is **oversize** if its 8th beat doesn't have `in_last` = 1. The router sets
`STATUS.OVERSIZE` in the cycle it accepts that beat, sends the 8th beat out with `out_last` = 1 if
the packet is being forwarded, and takes and throws away the rest, up to and including the beat with
`in_last` = 1. An oversize packet that is also dropped is counted once as a drop and sets
`STATUS.OVERSIZE` too; oversize packets aren't counted in `DROP_CNT`
([Oversize packets](router-spec.md#oversize-packets)).

## Timing

| What | When | In the specification |
|---|---|---|
| `in_ready` between packets | equals `CTRL.EN`, which resets to 0 | [Enabling the router](router-spec.md#enabling-the-router) |
| `in_ready` inside a packet | 1 from its first handshake to its last, whatever `CTRL.EN`, the routes and the outputs do | rule I6 |
| A beat into an empty output | on the pins 2 cycles after its input handshake (E2) | [The outputs](router-spec.md#the-outputs) |
| Beat $k$ of an output | on the pins from cycle $\max(t_k + 2,\; h_{k-1} + 1)$ until the cycle $h_k$ it's taken, where $t_k$ is its input handshake | rule O8 |
| A stalled output | holds its beat, unchanged, until the sink takes it; the other output and the input carry on | rules O1, O2, O7 |
| An APB write | 2 cycles (setup, one access cycle); the register changes at the edge that ends the access cycle | [APB](router-spec.md#apb) |
| An APB read | 3 cycles (setup, two access cycles); it returns the value the register had in the first access cycle | rule A8 |
| A drop, or an oversize packet | its `STATUS` bit (and for a drop, its counter) changes from the cycle after the header, or after the 8th beat | E4, E5, E6 |
| `irq` | in the same cycle as the `STATUS` or `INT_EN` bit that changes it | [INT_EN](router-spec.md#int_en) |

## Register map

Addresses are byte addresses, every register is 32 bits, and bits not listed read 0 and ignore
writes ([Register map](router-spec.md#register-map)).

| Address | Register | Access | Reset | Fields | UVM access |
|---|---|---|---|---|---|
| `0x00` | `ID` | read-only | `0xD105_0001` | [31:0] design 105, revision 1 | `RO` |
| `0x04` | `CTRL` | read-write | 0 | [0] `EN` | `RW` |
| `0x08` | `STATUS` | write 1 to clear | 0 | [0] `NOROUTE`, [1] `FULL`, [2] `OVERSIZE` | `W1C`, volatile |
| `0x0C` | `INT_EN` | read-write | 0 | [0] `NOROUTE`, [1] `FULL`, [2] `OVERSIZE` | `RW` |
| `0x10` | `DROP_CNT` | read-only; any write clears both | 0 | [7:0] `NOROUTE_CNT`, [15:8] `FULL_CNT` | `WC`, volatile |
| `0x14` | `LEVEL` | read-only | 0 | [4:0] `LEVEL0`, [12:8] `LEVEL1` | `RO`, volatile |
| `0x20`, `0x24`, `0x28`, `0x2C` | `ROUTE0` to `ROUTE3` | read-write | 0 | [0] `EN`, [1] `PORT` | `RW` |

The other 246 of the 256 addresses are bad: `0x18`, `0x1C`, everything from `0x30` to `0xFF`, and
every address that isn't a multiple of 4. A transfer to a bad address takes the same number of
cycles as any other and completes with `pslverr` = 1; a bad write changes nothing, and a bad read
returns 0. Writing `ID`, `LEVEL` or the reserved bits of any register isn't an error: the transfer
completes with `pslverr` = 0 and the write is ignored.

Four details of the registers catch people out:

- $\texttt{irq} = \bigvee_{i} (\texttt{STATUS}[i] \wedge \texttt{INT\_EN}[i])$, with no delay.
  `INT_EN` doesn't stop `STATUS` recording events; it only decides which ones raise `irq`.
- If an event sets a `STATUS` bit in the cycle a write clears it, the event wins and the bit stays 1
  ([STATUS](router-spec.md#status)).
- A write to `DROP_CNT` in the cycle of a drop clears the counter first and then counts the drop, so
  it reads 1 afterwards (E9, [DROP_CNT](router-spec.md#drop_cnt)).
- `PORT` keeps its value while `EN` is 0, but has no effect then
  ([ROUTE0 to ROUTE3](router-spec.md#route0-to-route3)).

## Reset

`rst_n` is asynchronous: when it falls, the whole router resets at once, without waiting for an
edge, and it runs normally from the first rising edge after `rst_n` is 1 again. While it's low,
`in_ready`, both `out_valid`s, `irq`, `pslverr` and `prdata` are 0 and `pready` is 1 (with the bus
idle). Every register goes back to its reset value, so every route is disabled and `CTRL.EN` is 0,
and nothing gets through until software sets them up again. Both buffers are emptied, and a packet
in flight is lost: nothing from before the reset ever comes out afterwards, including a beat that
was waiting on a stalled output (E8). Hold `rst_n` low through at least one rising edge at the start
of every simulation ([Reset](router-spec.md#reset)).

## The rules

These are the rules that [Valid/ready rules](router-spec.md#validready-rules) and
[APB rules](router-spec.md#apb-rules) number, one line each. The ones marked *testbench* are your
stimulus's job, and the router assumes them without checking. The specification says how each kind
is best checked: most are one- or two-cycle properties that make plain assertions, O5, O6 and O8
need per-output state that belongs in a scoreboard, and I4, O3 and O7 say what a signal does not
depend on, which only a model or a mid-cycle test can show. The rules about normal operation hold
only while `rst_n` is 1; I7, the first halves of O4 and A4, and the reset values say what holds while
it's 0.

| Rule | Whose | What it says |
|---|---|---|
| I1 | testbench | Once `in_valid` is 1, it stays 1 until the handshake or a reset. |
| I2 | testbench | While `in_valid` is 1 and `in_ready` is 0, `in_data` and `in_last` don't change. |
| I3 | testbench | After a reset, the first beat the source offers is the header of a new packet. |
| I4 | router | `in_ready` doesn't depend on `in_valid`, `in_data` or `in_last` in the same cycle. |
| I5 | router | Between packets, `in_ready` equals `CTRL.EN`. |
| I6 | router | From a packet's first handshake to its last, `in_ready` is 1, unless a reset comes. |
| I7 | router | `in_ready` is 0 while `rst_n` is 0. |
| O1 | router | Once `out_valid` is 1, it stays 1 until the handshake or a reset. |
| O2 | router | While `out_valid` is 1 and `out_ready` is 0, `out_data` and `out_last` don't change. |
| O3 | router | `out_valid`, `out_data` and `out_last` don't depend on any input in the same cycle. |
| O4 | router | `out_valid` is 0 during reset, and after it until a beat accepted after the reset arrives. |
| O5 | router | An output delivers its packets' beats in the order the router accepted them, unchanged except a cut packet's `out_last`, and never interleaved. |
| O6 | router | Every output packet is 1 to 8 beats and ends with the only beat that has `out_last` = 1, unless a reset cuts it short. |
| O7 | router | Nothing about output 0 depends on `out1_ready`, or about output 1 on `out0_ready`. |
| O8 | router | Beat $k$ is on the output from cycle $\max(t_k + 2, h_{k-1} + 1)$ until it's taken, and `out_valid` is 0 otherwise. |
| A1 | testbench | A transfer is one setup cycle followed at once by its access cycles. |
| A2 | testbench | `paddr`, `pwrite` and a write's `pwdata` hold from the setup cycle to the end of the transfer. |
| A3 | testbench | In the cycle after a transfer completes, `penable` is 0. |
| A4 | testbench | `psel` is 0 during reset; a transfer cut by a reset has no effect. |
| A5 | router | In a write's first access cycle, `pready` is 1. |
| A6 | router | In a read's first access cycle `pready` is 0, and in its second it's 1; it's 0 at no other time. |
| A7 | router | `pslverr` is 1 only in the cycle a transfer to a bad address completes. |
| A8 | router | A completing read's `prdata` is the register's value in the first access cycle (0 for a bad address), and `prdata` changes only then and at reset. |
| A9 | router | A good write takes effect at the end of its access cycle, by the register's access type. |

## Check yourself

1. `ROUTE0` is `0x1` and `CTRL.EN` is 1, output 0 is stalled, and it holds seven 1-beat packets. An
   8-beat packet for `DST` 0 arrives, then a 1-beat one. What happens to each?

   <details>
   <summary>Answer</summary>

   The 8-beat packet's header sees a level of 7, which is 8 or less, so it's admitted and the level
   goes to 15. The 1-beat packet's header then sees 15, so it's dropped as FULL: `FULL_CNT` goes up
   by one and `STATUS.FULL` is set from the next cycle.

   </details>

2. All four routes are disabled and output 1 is full. A packet for `DST` 3, whose `ROUTE3.PORT` is
   1, comes in. Which counter goes up?

   <details>
   <summary>Answer</summary>

   `NOROUTE_CNT`, and only that one. A disabled route is NOROUTE whatever the level of the output
   its `PORT` names.

   </details>

3. Your test writes `0x3` to `ROUTE1`, and the write completes in the same cycle a header with
   `DST` 1 is accepted. Before the write, `ROUTE1` was 0. Where does the packet go?

   <details>
   <summary>Answer</summary>

   Nowhere: it's dropped as NOROUTE. A header accepted in the cycle a write completes uses the old
   value, and the new one applies from the next cycle on.

   </details>
