"""Step one: chopping the text into words.

Before anything can make sense of a programme, the text has to be split
into the smallest pieces that mean something on their own. `let x = 42` is
four of them: the keyword `let`, the name `x`, the symbol `=`, and the
number `42`. Those pieces are called **tokens**, and this is what produces
them.

Everything after this point works on tokens rather than on characters,
which is why the grammar in `parser.py` never has to think about spaces or
comments.

Most of the work is one regular expression with a named group per kind of
token, tried in the order written. Two of OCaml's rules need real code, and
they are the reason this is a separate file rather than part of the
grammar:

* **Comments nest.** `(* a (* b *) c *)` is one comment, which no regular
  expression can say. `skip_comment` counts the pairs.
* **`'a'` is a character and `'a` is a type variable.** One ordered choice
  settles it: a character literal has a closing quote and a type variable
  never does, so the character pattern is tried first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORDS = frozenset({
    "and",
    "as",
    "asr",
    "begin",
    "do",
    "done",
    "downto",
    "else",
    "end",
    "exception",
    "false",
    "for",
    "fun",
    "function",
    "if",
    "in",
    "land",
    "let",
    "lor",
    "lsl",
    "lsr",
    "lxor",
    "match",
    "mod",
    "mutable",
    "of",
    "rec",
    "then",
    "to",
    "true",
    "try",
    "type",
    "when",
    "while",
    "with",
})

#: Longest first, so `->` beats `-` and `.(` beats `.`. Kept as a tuple
#: because the order is the rule, and a set would lose it.
SYMBOLS = (
    "->", "<-", ":=", "::", ";;", "||", "&&", "<=", ">=", "<>", "**",
    "+.", "-.", "*.", "/.", "[|", "|]", ".(", ".[",
    "(", ")", "[", "]", "{", "}", ",", ";", ":", "|", "=", "<", ">",
    "+", "-", "*", "/", "^", "@", "!", ".", "_",
)  # fmt: skip

_ESCAPE = r"\\(?:[\\'\"ntbr ]|\d{3}|x[0-9A-Fa-f]{2})"

_TOKEN = re.compile(
    r"""
      (?P<float> \d[\d_]* (?: \. [\d_]* (?:[eE][+-]?\d+)? | [eE][+-]?\d+ ) )
    | (?P<int>   0[xX][0-9A-Fa-f_]+ | 0[oO][0-7_]+ | 0[bB][01_]+ | \d[\d_]* )
    | (?P<char>  ' (?: {escape} | [^\\'] ) ' )
    | (?P<tyvar> ' [a-z_][A-Za-z0-9_']* )
    | (?P<string> " (?: {escape} | \\\n[ \t]* | [^"\\] )* " )
    | (?P<lid>   [a-z_][A-Za-z0-9_']* )
    | (?P<uid>   [A-Z][A-Za-z0-9_']* )
    | (?P<sym>   {symbols} )
    """.format(
        escape=_ESCAPE,
        symbols="|".join(re.escape(s) for s in SYMBOLS),
    ),
    re.VERBOSE,
)

_UNESCAPE = {
    "n": "\n", "t": "\t", "b": "\b", "r": "\r",
    "\\": "\\", "'": "'", '"': '"', " ": " ",
}  # fmt: skip


class LexError(SyntaxError):
    """The source is not caml-prépa."""


@dataclass(frozen=True)
class Token:
    #: One of: int float char string lid uid tyvar kw sym eof
    kind: str
    text: str
    #: Offset into the source, for error messages.
    at: int
    #: The value a literal denotes. None for everything else.
    value: object = None


def where(source: str, at: int) -> str:
    """`line:column`, counted from the offset a token carries."""
    line = source.count("\n", 0, at) + 1
    column = at - (source.rfind("\n", 0, at) + 1) + 1
    return f"{line}:{column}"


def skip_comment(source: str, at: int) -> int:
    """The offset just past a `(* ... *)`, counting nested pairs."""
    depth = 0
    start = at
    while at < len(source):
        if source.startswith("(*", at):
            depth += 1
            at += 2
        elif source.startswith("*)", at):
            depth -= 1
            at += 2
            if depth == 0:
                return at
        else:
            at += 1
    raise LexError(f"unterminated comment at {where(source, start)}")


def unescape(text: str) -> str:
    """The characters a literal's body denotes."""
    out: list[str] = []
    at = 0
    while at < len(text):
        if text[at] != "\\":
            out.append(text[at])
            at += 1
            continue
        head = text[at + 1]
        if head == "x":
            out.append(chr(int(text[at + 2 : at + 4], 16)))
            at += 4
        elif head.isdigit():
            out.append(chr(int(text[at + 1 : at + 4])))
            at += 4
        elif head == "\n":
            at += 2
            while at < len(text) and text[at] in " \t":
                at += 1
        else:
            out.append(_UNESCAPE[head])
            at += 2
    return "".join(out)


def _value(kind: str, text: str) -> object:
    """What a literal token denotes, or None for a token that is not one."""
    match kind:
        case "int":
            return int(text.replace("_", ""), 0)
        case "float":
            return float(text.replace("_", ""))
        case "char":
            return unescape(text[1:-1])
        case "string":
            return unescape(text[1:-1])
    return None


def tokenize(source: str) -> list[Token]:
    """Every token of `source`, ending with one of kind `eof`."""
    out: list[Token] = []
    at = 0
    while at < len(source):
        if source[at].isspace():
            at += 1
            continue
        if source.startswith("(*", at):
            at = skip_comment(source, at)
            continue
        found = _TOKEN.match(source, at)
        if found is None:
            raise LexError(f"stray {source[at]!r} at {where(source, at)}")
        kind = found.lastgroup
        text = found.group()
        assert kind is not None
        match kind:
            case "lid" if text in KEYWORDS:
                kind = "kw"
            case "lid" if text == "_":
                kind = "sym"
        out.append(Token(kind, text, at, _value(kind, text)))
        at = found.end()
    out.append(Token("eof", "", len(source)))
    return out
