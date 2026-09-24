"""Wirth's P-machine, and the assembler that resolves labels for it.

A stack, and a frame per active procedure holding three words of header
before its locals:

    0  static link   the frame of the lexically enclosing procedure
    1  dynamic link  the caller's frame
    2  return address

`LOD 2 4` means "the variable at offset 4, two levels out", and the static
link chain is what makes two levels out reachable. That addressing is the
reason PL/0 needs a scope tree at all, and it is what `analyze.py` computes.
"""

from __future__ import annotations

import operator

BINARY = {
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    # PL/0 divides integers, truncating towards zero as Pascal does.
    "div": lambda a, b: abs(a) // abs(b) * (1 if (a < 0) == (b < 0) else -1),
    "eq": lambda a, b: int(a == b),
    "ne": lambda a, b: int(a != b),
    "lt": lambda a, b: int(a < b),
    "le": lambda a, b: int(a <= b),
    "gt": lambda a, b: int(a > b),
    "ge": lambda a, b: int(a >= b),
}


def assemble(lines: list[str]) -> list[tuple[str, ...]]:
    """Resolve `label:` definitions into addresses, and drop them."""
    labels: dict[str, int] = {}
    body: list[list[str]] = []
    for line in lines:
        if line.endswith(":"):
            labels[line[:-1]] = len(body)
        else:
            body.append(line.split())
    out: list[tuple[str, ...]] = []
    for parts in body:
        resolved = parts
        if parts[0] in {"JMP", "JPC", "CAL"} and parts[-1] in labels:
            resolved = [*parts[:-1], str(labels[parts[-1]])]
        out.append(tuple(resolved))
    return out


def run(lines: list[str], *, limit: int = 200_000) -> list[int]:
    """Execute, returning everything the program wrote."""
    code = assemble(lines)
    stack: list[int] = [0, 0, 0]
    base, pc, written, steps = 0, 0, [], 0

    def outer(levels: int, frame: int) -> int:
        for _ in range(levels):
            frame = stack[frame]
        return frame

    while pc < len(code):
        steps += 1
        if steps > limit:
            raise RuntimeError("program did not terminate")
        instruction = code[pc]
        pc += 1
        match instruction:
            case ("LIT", value):
                stack.append(int(value))
            case ("LOD", levels, offset):
                stack.append(stack[outer(int(levels), base) + int(offset)])
            case ("STO", levels, offset):
                stack[outer(int(levels), base) + int(offset)] = stack.pop()
            case ("INT", size):
                stack.extend([0] * (int(size) - 3))
            case ("OPR", "neg"):
                stack.append(-stack.pop())
            case ("OPR", "odd"):
                stack.append(stack.pop() % 2)
            case ("OPR", name):
                right = stack.pop()
                stack.append(BINARY[name](stack.pop(), right))
            case ("JMP", target):
                pc = int(target)
            case ("JPC", target):
                if stack.pop() == 0:
                    pc = int(target)
            case ("CAL", levels, target):
                # The static link is `levels` out from here, which is the frame
                # of the procedure declaring the callee. The dynamic link is
                # simply the caller.
                stack.extend([outer(int(levels), base), base, pc])
                base = len(stack) - 3
                pc = int(target)
            case ("RET",):
                top = base
                pc, base = stack[top + 2], stack[top + 1]
                del stack[top:]
            case ("WRT",):
                written.append(stack.pop())
            case ("HALT",):
                break
            case _:
                raise RuntimeError(f"unknown instruction {' '.join(instruction)}")
    return written
