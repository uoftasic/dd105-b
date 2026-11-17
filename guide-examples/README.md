# Guide examples

This folder holds the examples that DD105-B's guide and reference pages quote. Each folder belongs to
one page and has the page's name. Every folder has a `Makefile` that includes the labs' shared
[`labs/common/pyuvm.mk`](../labs/common/README.md), so it builds with Verilator 5.050 and runs
with cocotb 2.0.1 and pyuvm 4.0.1 in the course image, and it has the same targets as a lab
(`make build`, `make run`, `make clean` and the rest). One build serves every test in a folder, and
`TEST=` picks the test when you run.

The pages are for reading, and none of them asks you to run anything here. The sections below give
the commands that produced each output a page quotes, so the folders are for anyone who wants to
check what a page says, or to change an example and see what happens. Run each command from the
example's folder, in the course image, and finish with `make clean`.

## pyuvm-register-api

Page: [The pyuvm register API](../docs/reference/pyuvm-register-api.md), a reference page.
Six pyuvm tests in `tb/test_regapi.py`, on the golden router. The bus side is
[`labs/ref`](../labs/ref/README.md)'s APB agent, register model and adapter, which `PY_DIRS` puts
on the path; none of them needs the course venv. Every line the tests print starts with `REGAPI`,
and each test catches what an operation raises and prints it, so every run ends with `ok`.

| Command | What the page quotes |
|---|---|
| `make run TEST=RegPolicyTest` | `predict()` on a field of each of the 26 access policies; `predict()`'s `kind` and `path` arguments; what `configure()`, `add_reg()`, `map.reset()`, `add_hdl_path()` and `uvm_mem` refuse; which methods and classes exist |
| `make run TEST=RegOpsTest` | `read()` and `write()` through the map, what `reg2bus()` receives, the mirror after each, `set_desired()` with `write(None, ...)`, and `uvm_door_e` passed as a path |
| `make run TEST=RegTwoOpsTest` | two operations on one register at once, and on two registers |
| `make run TEST=RegBackdoorTest` | `path_t.BACKDOOR` and `path_t.USER_FRONTDOOR`, and the register they leave stuck |
| `make run TEST=RegAutoPredictTest` | `enable_auto_predict` set in each of the two modules that hold it |
| `make run TEST=RegAddrTest` | registers configured at `"0x00"`, and added at an offset, and the map's base address |

`grep REGAPI build/runs/<test>-s1/run.log` pulls a test's lines out of its log. In the course image
with 2 CPUs and 3 GB, `make build` took 7.8 s with an empty ccache, and each run took 0.31 s to
1.17 s.
