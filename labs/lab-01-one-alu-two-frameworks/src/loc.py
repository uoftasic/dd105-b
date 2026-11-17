"""
DD105-B Lab 01: count a testbench's lines.

    python3 src/loc.py FILE...        (or `make loc`)

For each file it prints two numbers: every line (what `wc -l` says), and the
code lines, which are the lines left after dropping blank lines and comments.
For Python a docstring counts as a comment; for SystemVerilog both `//` and
`/* ... */` comments are dropped. A line with code and a comment on it counts
as code.
"""

import io
import os
import sys
import tokenize


def python_code_lines(text):
    """Line numbers that hold Python code, not comments or docstrings."""
    code = set()
    prev = tokenize.INDENT
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        kind = tok.type
        if kind in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.ENDMARKER):
            if kind in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                prev = kind
            continue
        # A string that is a statement by itself is a docstring.
        if kind == tokenize.STRING and prev in (tokenize.NEWLINE, tokenize.INDENT,
                                                tokenize.DEDENT):
            prev = None
            continue
        prev = kind
        code.update(range(tok.start[0], tok.end[0] + 1))
    return code


def sv_code_lines(text):
    """Line numbers that hold SystemVerilog code, not comments."""
    code = set()
    line, i, n = 1, 0, len(text)
    in_block = in_string = False
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            in_string = False
        elif in_block:
            if text.startswith("*/", i):
                in_block = False
                i += 1
        elif in_string:
            code.add(line)
            if c == "\\":
                i += 1
            elif c == '"':
                in_string = False
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            in_block = True
            i += 1
        elif c == '"':
            in_string = True
            code.add(line)
        elif not c.isspace():
            code.add(line)
        i += 1
    return code


def count(path):
    text = open(path, errors="replace").read()
    total = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    lines = python_code_lines(text) if path.endswith(".py") else sv_code_lines(text)
    return total, len(lines)


def main(paths):
    if not paths:
        sys.exit(__doc__)
    width = max(len(p) for p in paths)
    print(f"  {'file':<{width}}  {'lines':>6}  {'code':>6}")
    t_all = t_code = 0
    for p in paths:
        if not os.path.exists(p):
            sys.exit(f"loc.py: no such file: {p}")
        total, code = count(p)
        t_all += total
        t_code += code
        print(f"  {p:<{width}}  {total:>6}  {code:>6}")
    if len(paths) > 1:
        print(f"  {'total':<{width}}  {t_all:>6}  {t_code:>6}")


if __name__ == "__main__":
    main(sys.argv[1:])
