# Modules

| module | what it provides |
| --- | --- |
| `grammar` | the `Grammar` type, the three ways to declare one, and every structural query |
| `astero.python` | Python's grammar, ready to use: roles authored, sorts and shapes read from the `ast` module itself |
| `rewriting` | `Pass` and the rule engine; recomputes `ctx` from the grammar's roles |
| `scopes` | the scope tree, and the names each block binds |
| `hygiene` | capture-avoiding substitution, renaming across every declared slot, fresh-name supplies |
| `coverage` | what a dispatch table covers of a grammar, and what it misses |
| `emit` | the document tree, the renderer, and the bracketing rule; it holds no operator table, so it knows no language |
| `astero.python.precedence` | Python's operator table, and the three questions that read it |
| `astero.python.emit` | a Python expression emitter whose brackets come from that table |
| `emit_rules` | a code generator written as guarded templates over the grammar |
| `tables` | `Family`, for operation-by-type matrices that no grammar derives |
| `testing` | sample programs exercising every declared position; `missing_coverage` returns the positions your tests have not reached |

## Entry points

```python
from astero.python import Pass, Match, Strategy, rules, rewrite, DELETE
from astero.grammar import (
    Grammar,
    GrammarBuilder,
    from_dataclasses,
    Kind,
    Shape,
    Field,
    defines,
    uses,
    deletes,
    declares,
    Present,
    Absent,
)
from astero.python import PY, VARS, ATTRS, SCOPES, BINDING_SCOPES, build, mangle
from astero.python import annotation_blocks  # PEP 649, from 3.14
from astero.scopes import (
    Scope,
    Block,
    scope_tree,
    binds_in_scope,
    names_bound_by,
    bound_names,
)
from astero.python.hygiene import substitute, rename, Fresh, free_names, bound_here
from astero.python.hygiene import CaptureError
from astero.coverage import Coverage, dispatch, handlers, match_arms, visitors
from astero.emit_rules import Emitter, EmitError
from astero.emit_rules import All, Both, Either, Not, Is, OpIs, Const, Has
from astero.emit import Doc, Level, Assoc, ATOM, FREE, render, text, nest, spans
from astero.emit import needs_parens
from astero.python.precedence import PRECEDENCE, level_of
from astero.python.emit import emit, emit_module
from astero.tables import Family
from astero.testing import snippets, combinations, missing_coverage
```

Every symbol above has a generated page under [API](../api/grammar.md), rendered from its own docstring.

## Version sensitivity

astero is tested on Python 3.11 through 3.15, unit and integration alike. What differs between them:

- Each AST class's `_field_types` exists from **3.13**. On 3.11 and 3.12 every field shape is `UNKNOWN`.
- Comprehensions stopped opening a scope in **3.12** (PEP 709), which is why `SCOPES` and `BINDING_SCOPES` are separate tables.
- PEP 695 type-parameter blocks are named `type parameter` on **3.12** and `type parameters` from **3.13**.
- `symtable.get_type()` returns a string before **3.13** and an enum after.
- PEP 649 adds `annotation` blocks from **3.14**, unless the module carries `from __future__ import annotations`. Pass `astero.python.annotation_blocks(tree)` as `scope_tree`'s `siblings`.
- **3.15** renamed the blocks CPython names itself: `genexpr` became `<genexpr>` and `lambda` became `<lambda>`.
- `TypeVar`, `ParamSpec` and `TypeVarTuple` are productions from **3.12**, so `ident_slots(VARS)` reports 12 productions on 3.11 and 15 from 3.12.
