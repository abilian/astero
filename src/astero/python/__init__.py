"""Python, declared: CPython's node table plus the roles it omits.

The rest of `astero` is language-agnostic — `astero.grammar` declares any
syntax tree, `astero.scopes` walks any of them, `astero.emit` is a document
algebra with a bracketing rule that knows no operators. This package is the
one language that ships with the library, and the front door for it:

    from astero.python import PY, VARS

`lang` is the grammar itself: 124 productions read from the interpreter, 38
fields carrying a role, 22 positions that introduce a name. `precedence` is
Python's operator table and the three questions that read it. `emit` is a
Python expression emitter whose brackets come from that table rather than
from the templates.

For a language that is not Python, declare your own: `examples/pl0` does it
in one table over annotated dataclasses, and shares nothing with this package.
"""

from __future__ import annotations

from astero.python.hygiene import (
    CaptureError,
    Fresh,
    free_names,
    rename,
    substitute,
)
from astero.python.lang import (
    ANNOTATION_BLOCKS,
    ATTRS,
    BINDING_POSITIONS,
    BINDING_SCOPES,
    CONDITIONS,
    DEFUSE_POSITIONS,
    DELETING_POSITIONS,
    DEPRECATED_ALIASES,
    DERIVED_FIELDS,
    DOTTED_POSITIONS,
    IDENT,
    IDENT_POSITIONS,
    PY,
    SCOPES,
    VARS,
    annotation_blocks,
    build,
    defers_annotations,
    mangle,
)

# `rewriting.build` is deliberately absent: `lang.build` makes a grammar from a
# module and `rewriting.build` makes a tree from a template, and one namespace
# cannot hold both. The second is reached as `astero.python.rewriting.build`.
from astero.python.rewriting import (
    DELETE,
    DERIVED,
    Match,
    Pass,
    Rule,
    Strategy,
    fix_contexts,
    key,
    match,
    rewrite,
    rule,
    rules,
    target_fields,
)

__all__ = [
    "ANNOTATION_BLOCKS",
    "ATTRS",
    "BINDING_POSITIONS",
    "BINDING_SCOPES",
    "CONDITIONS",
    "DEFUSE_POSITIONS",
    "DELETE",
    "DELETING_POSITIONS",
    "DEPRECATED_ALIASES",
    "DERIVED",
    "DERIVED_FIELDS",
    "DOTTED_POSITIONS",
    "IDENT",
    "IDENT_POSITIONS",
    "PY",
    "SCOPES",
    "VARS",
    "CaptureError",
    "Fresh",
    "Match",
    "Pass",
    "Rule",
    "Strategy",
    "annotation_blocks",
    "build",
    "defers_annotations",
    "fix_contexts",
    "free_names",
    "key",
    "mangle",
    "match",
    "rename",
    "rewrite",
    "rule",
    "rules",
    "substitute",
    "target_fields",
]
