"""The front end: text in, a tree out.

Three files do that, in order. `lexer` chops the text into tokens, `peg` is
the engine, and `parser` is the grammar written on top of it. `emit` goes
the other way, turning a tree back into text, and it belongs here because
its brackets come from the parser's own precedence table and because
printing-then-reparsing is how the parser is checked.
"""

from __future__ import annotations
