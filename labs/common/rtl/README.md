# `labs/common/rtl`: the packet router

The design you verify in DD105. Its specification is the reference page
[The packet router](../../../docs/reference/router-spec.md); write testbenches from that page, not
from these files.

| File | What it holds |
|---|---|
| `router_pkg.sv` | Sizes, register offsets and the ingress state type |
| `router_fifo.sv` | One output buffer (a 15-entry RAM and an output register) and the stream it drives |
| `router_ingress.sv` | The input stream: route lookup, admission, drops and the 8-beat length limit |
| `router_regs.sv` | The APB port and every register |
| `router.sv` | The top module, `router` |
| `router.f` | The files in compile order. Its paths are relative to this folder, so use `-F`, not `-f` |

```bash
verilator --lint-only -Wall -F labs/common/rtl/router.f --top-module router
```

The lint passes with no warnings. The one waiver, in `router_regs.sv`, is for the bits of `pwdata`
that no register uses, and its comment says why.

These files are the golden design. The planted bugs are not in them: `../inject.py` adds them to a
copy (see `../bugs.py`), so if you change a line here, run `python3 ../inject.py --verify` to check
that every bug's anchor line still matches.
