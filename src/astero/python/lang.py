"""Python's grammar, declared: CPython's node table plus the roles it omits.

**Not a parser, and not a replacement for `ast`.** `ast` already answers what
fields a production has and what each holds: `Assign.targets` is `list[expr]`
and `Assign.value` is `expr`. What it cannot answer is that the first
introduces a name and the second does not. To `ast` the two are both `expr`,
and the difference between them exists only in the language reference and in
the head of whoever writes the pass.

Supplying that difference is the whole content of this module. Of Python's 176
fields across 124 productions, **138 are `child`** and have nothing to say; the
other 38 carry a role, and 22 positions introduce a variable name — from the
obvious `Assign.targets` to `MatchMapping.rest`, `comprehension.target` and
`withitem.optional_vars`. That list is what every Python tool re-derives by
hand, and what it misses one of.

The rest is machinery to avoid restating what CPython already records: sorts
and shapes come from the running interpreter, roles are authored here. The
stdlib cannot be annotated in place, so the role table is the one piece written
by hand, and `tests/a_unit/test_lang_py.py` gates it against CPython's own
parser.

Sorts and shapes are free from `ast._field_types` on 3.13 and later. On 3.11
and 3.12 only field *names* are exposed, so `Field.sort` is None there and the
identifier sorts are supplied by the same role table that names the positions.
That costs nothing here, because every derivation this module feeds keys off
roles rather than sorts.
"""

from __future__ import annotations

import _ast
import ast
import sys
from dataclasses import replace
from types import ModuleType

from astero.grammar import (
    ATTR,
    CHILD,
    Absent,
    Condition,
    Field,
    Grammar,
    GrammarBuilder,
    Present,
    Role,
    Shape,
    declares,
    defines,
    defuse,
    deletes,
    shape_of,
    uses,
)
from astero.scopes import DOTTED, Scope

#: The one namespace Python resolves lexically.
VARS = "vars"
#: Attribute names. Marked so renaming can see them, never resolved statically.
ATTRS = "attrs"

#: Terminal sort for a bare identifier.
IDENT = "ident"

# --------------------------------------------------------------------- roles
#
# Authored. Everything not named here is a plain `child` or `attr`, decided by
# whether the field holds AST nodes.
#
# A field appears once, under the production that owns the position. That is
# the whole point: `ctx` is not a property of a `Name`, it is a property of
# where the `Name` sits.

BINDING_POSITIONS: dict[str, tuple[str, ...]] = {
    "Assign": ("targets",),
    "AnnAssign": ("target",),
    "For": ("target",),
    "AsyncFor": ("target",),
    "NamedExpr": ("target",),
    "comprehension": ("target",),
    "withitem": ("optional_vars",),
    # 3.12's `type X = ...`. Absent on 3.11, and skipped when absent.
    "TypeAlias": ("name",),
}

DELETING_POSITIONS: dict[str, tuple[str, ...]] = {
    "Delete": ("targets",),
}

#: Read and written in one position.
DEFUSE_POSITIONS: dict[str, tuple[str, ...]] = {
    "AugAssign": ("target",),
}

#: Fields holding a bare identifier string, each with its own role. Every
#: position renaming has to reach, and whether each one binds or refers.
#: `Grammar.ident_slots(ns)` reads them back out.
#:
#: `Name.id` defaults to a use. When a `Name` sits in a binding position the
#: parent's field says so, which is the layering that makes `ctx` derivable.
IDENT_POSITIONS: dict[str, dict[str, Role]] = {
    "Name": {"id": uses(VARS)},
    "arg": {"arg": defines(VARS)},
    "FunctionDef": {"name": defines(VARS)},
    "AsyncFunctionDef": {"name": defines(VARS)},
    "ClassDef": {"name": defines(VARS)},
    "Attribute": {"attr": uses(ATTRS)},
    "keyword": {"arg": uses(ATTRS)},
    # `import a.b` binds `a`; `import a.b as c` binds `c` and not `a`. The
    # binder therefore depends on a sibling field, which a per-field role
    # cannot say. `ALIAS_BINDS` carries that one rule instead.
    "alias": {"name": defines(VARS), "asname": defines(VARS)},
    "ExceptHandler": {"name": defines(VARS)},
    # `global x` and `nonlocal x` say the name is *not* owned here.
    "Global": {"names": declares(VARS)},
    "Nonlocal": {"names": declares(VARS)},
    "MatchAs": {"name": defines(VARS)},
    "MatchStar": {"name": defines(VARS)},
    "MatchMapping": {"rest": defines(VARS)},
    "TypeVar": {"name": defines(VARS)},
    "ParamSpec": {"name": defines(VARS)},
    "TypeVarTuple": {"name": defines(VARS)},
}

#: Productions that open a lexical scope, and which of their fields are
#: evaluated inside it. Everything not listed in `inside` belongs to the
#: enclosing scope, which is how `def f(...)` binds `f` outside while binding
#: its parameters inside, and how a decorator or a default argument is
#: evaluated where the function is defined rather than where it runs.
#:
#: PEP 709 inlined list, set and dict comprehensions in 3.12, so they open a
#: scope on 3.11 and do not after. A generator expression always does.
_COMPREHENSIONS_ARE_SCOPES = sys.version_info < (3, 12)

#: 3.15 put angle brackets round the blocks CPython names itself.
_GENEXPR = "<genexpr>" if sys.version_info >= (3, 15) else "genexpr"
_LAMBDA = "<lambda>" if sys.version_info >= (3, 15) else "lambda"

#: CPython spells the PEP 695 block "type parameter" on 3.12 and
#: "type parameters" from 3.13.
_TYPE_PARAMS_KIND = (
    "type parameter" if sys.version_info < (3, 13) else "type parameters"
)

_TYPE_PARAMS = Scope(
    _TYPE_PARAMS_KIND,
    inside=("type_params", "bases", "keywords", "returns", "value"),
    name_field="name",
    when=Present("type_params"),
)

#: What a function computes where it is defined, although `args` is inside
#: it: its defaults, and its annotations (in the type-parameter scope when it
#: has one, which is the scope around the function's own).
_DEFAULTS = ("args.defaults", "args.kw_defaults")
_DEFINED_OUTSIDE = (
    *_DEFAULTS,
    "args.posonlyargs.*.annotation",
    "args.args.*.annotation",
    "args.kwonlyargs.*.annotation",
    "args.vararg.annotation",
    "args.kwarg.annotation",
)
#: A comprehension's first iterable, computed before it runs.
_FIRST_ITERABLE = ("generators.0.iter",)

_FUNCTION = Scope(
    "function", ("args", "body"), name_field="name", outside=_DEFINED_OUTSIDE
)

#: Layers, outermost first. A layer whose condition fails does not open.
SCOPES: dict[str, tuple[Scope, ...]] = {
    "FunctionDef": (_TYPE_PARAMS, _FUNCTION),
    "AsyncFunctionDef": (_TYPE_PARAMS, _FUNCTION),
    "ClassDef": (_TYPE_PARAMS, Scope("class", ("body",), name_field="name")),
    "Lambda": (
        Scope("function", ("args", "body"), fixed_name=_LAMBDA, outside=_DEFAULTS),
    ),
    "GeneratorExp": (
        Scope(
            "function",
            ("elt", "generators"),
            fixed_name=_GENEXPR,
            outside=_FIRST_ITERABLE,
        ),
    ),
}

if sys.version_info >= (3, 12):
    SCOPES["TypeAlias"] = (
        _TYPE_PARAMS,
        Scope("type alias", ("value",), name_field="name"),
    )

if _COMPREHENSIONS_ARE_SCOPES:
    SCOPES |= {
        "ListComp": (
            Scope(
                "function",
                ("elt", "generators"),
                fixed_name="listcomp",
                outside=_FIRST_ITERABLE,
            ),
        ),
        "SetComp": (
            Scope(
                "function",
                ("elt", "generators"),
                fixed_name="setcomp",
                outside=_FIRST_ITERABLE,
            ),
        ),
        "DictComp": (
            Scope(
                "function",
                ("key", "value", "generators"),
                fixed_name="dictcomp",
                outside=_FIRST_ITERABLE,
            ),
        ),
    }


#: PEP 649, from Python 3.14: annotations are evaluated lazily, in a function
#: named `__annotate__` that lives in the *enclosing* block. `symtable` reports
#: one such block per `def`, immediately before the function's own, and one per
#: block that has annotated assignments, however many it has.
#:
#: It is a sibling rather than a `Scope` layer because it does not wrap what
#: the production contains, and it is here rather than in `SCOPES` because a
#: production that only contributes one is not itself a scope: `AnnAssign`
#: must not gain the `scope` trait.
ANNOTATION_BLOCKS: dict[str, Scope] = {}
if sys.version_info >= (3, 14):
    _ANNOTATE = Scope("annotation", inside=(), fixed_name="__annotate__")
    ANNOTATION_BLOCKS = {
        "FunctionDef": _ANNOTATE,
        "AsyncFunctionDef": _ANNOTATE,
        # One per block, not one per statement: two annotated assignments in
        # the same body share a single `__annotate__`.
        "AnnAssign": replace(_ANNOTATE, once=True),
    }


def defers_annotations(tree: ast.AST) -> bool:
    """Whether `tree` evaluates its annotations lazily, per PEP 649.

    False before Python 3.14, and false for a module carrying `from __future__
    import annotations`: PEP 563 makes every annotation a string, so nothing
    is deferred and CPython compiles no `__annotate__` at all.
    """
    if sys.version_info < (3, 14):
        return False
    return not any(
        isinstance(stmt, ast.ImportFrom)
        and stmt.module == "__future__"
        and any(a.name == "annotations" for a in stmt.names)
        for stmt in getattr(tree, "body", [])
    )


def annotation_blocks(tree: ast.AST) -> dict[str, Scope]:
    """`ANNOTATION_BLOCKS` if they are in force for `tree`, otherwise none.

    Pass the result as `scope_tree`'s `siblings`. Whether the blocks exist is
    a property of the whole module rather than of any node, which is why this
    is a function of the tree and not an entry in a table.
    """
    return ANNOTATION_BLOCKS if defers_annotations(tree) else {}


#: The regions a name binds over, which is not the same table as `SCOPES`.
#:
#: `SCOPES` answers what `symtable` calls a block, and PEP 709 inlined list,
#: set and dict comprehensions in 3.12 so they stopped being blocks. It did not
#: change what they bind: the iteration variable still does not leak, on every
#: version. A pass asking "may I replace this name here" wants the second
#: question, so it wants this table.
BINDING_SCOPES: dict[str, tuple[Scope, ...]] = SCOPES | {
    "ListComp": (
        Scope(
            "function",
            ("elt", "generators"),
            fixed_name="listcomp",
            outside=_FIRST_ITERABLE,
        ),
    ),
    "SetComp": (
        Scope(
            "function",
            ("elt", "generators"),
            fixed_name="setcomp",
            outside=_FIRST_ITERABLE,
        ),
    ),
    "DictComp": (
        Scope(
            "function",
            ("key", "value", "generators"),
            fixed_name="dictcomp",
            outside=_FIRST_ITERABLE,
        ),
    ),
}


def mangle(name: str, class_name: str) -> str:
    """Python's private name mangling, as the compiler applies it.

    An identifier written `__x` inside `class C` is compiled as `_C__x`. A
    renaming pass that skips this renames a name the interpreter never sees.
    """
    if not name.startswith("__") or name.endswith("__"):
        return name
    stripped = class_name.lstrip("_")
    # A class named only with underscores mangles nothing.
    return f"_{stripped}{name}" if stripped else name


#: Roles that hold only under a condition. `import a.b` binds `a` while
#: `import a.b as c` binds `c` alone, so which field binds depends on a sibling.
CONDITIONS: dict[tuple[str, str], Condition] = {
    ("alias", "name"): Absent("asname"),
    ("alias", "asname"): Present("asname"),
}

#: Fields whose bound name is the head of a dotted path.
DOTTED_POSITIONS = {("alias", "name")}

#: Fields the parser fills in and nobody should author.
DERIVED_FIELDS = frozenset({
    "ctx",
    "lineno",
    "col_offset",
    "end_lineno",
    "end_col_offset",
    "type_comment",
})


#: Names `ast` still exposes that the parser cannot produce. `Num`, `Str`,
#: `Bytes`, `NameConstant` and `Ellipsis` became `Constant` in 3.8; `Index`,
#: `ExtSlice` and the `slice` sort left subscripts and `AugLoad`, `AugStore`,
#: `Param` left `expr_context`, all in 3.9; `Suite` left `mod`.
#:
#: Not a list. The real grammar is the C module `_ast` and the shims are
#: written in Python in `ast.py`, so this is read off the interpreter and
#: empties itself when CPython finally deletes them. Public because a consumer
#: comparing its own class table against `ast` needs the same distinction.
DEPRECATED_ALIASES: frozenset[str] = frozenset(
    name
    for name, cls in vars(ast).items()
    if isinstance(cls, type)
    and issubclass(cls, ast.AST)
    and not name.startswith("_")
    and getattr(_ast, name, None) is not cls
)


def _productions(module: ModuleType) -> dict[str, type[ast.AST]]:
    """Every production `module` declares, ghosts excluded.

    The `_ast` test applies only to `ast` itself. A compiler that generates
    its own node classes has none of them in `_ast`, and excluding its whole
    grammar is not the question being asked.
    """
    real = module is ast
    return {
        name: cls
        for name, cls in vars(module).items()
        if isinstance(cls, type)
        and issubclass(cls, ast.AST)
        and not name.startswith("_")
        and not (real and name in DEPRECATED_ALIASES)
    }


def _role_for(prod: str, fname: str):
    if fname in BINDING_POSITIONS.get(prod, ()):
        return defines(VARS)
    if fname in DELETING_POSITIONS.get(prod, ()):
        return deletes(VARS)
    if fname in DEFUSE_POSITIONS.get(prod, ()):
        return defuse(VARS)
    return IDENT_POSITIONS.get(prod, {}).get(fname)


def build(module: ModuleType = ast, name: str = "") -> Grammar:
    """Python's grammar as this interpreter reports it, plus the roles above.

    `module` is `ast` by default. A compiler that generates its own node
    classes passes its module instead, and authors nothing: the roles are facts
    about Python, and a generated class hierarchy holds the same fields under
    the same names. What differs is which productions exist, so a host missing
    one gets a grammar missing it too, and building that node fails at the
    rewrite rather than downstream.
    """
    builder = GrammarBuilder(
        name=name or f"python{'.'.join(map(str, sys.version_info[:2]))}",
        namespaces={VARS, ATTRS},
        # A dotted import name is an identifier position too: renaming has to
        # reach it, even though what it *binds* is only the head.
        ident_sorts={IDENT, DOTTED},
    )
    for prod_name, cls in _productions(module).items():
        types = getattr(cls, "_field_types", None)
        fields = []
        for fname in cls._fields:
            if fname in DERIVED_FIELDS:
                continue
            role = _role_for(prod_name, fname)
            is_ident = fname in IDENT_POSITIONS.get(prod_name, {})
            sort = IDENT if is_ident else None
            when = CONDITIONS.get((prod_name, fname))
            if (prod_name, fname) in DOTTED_POSITIONS:
                sort = DOTTED
            shape = Shape.UNKNOWN
            if types is not None and fname in types:
                shape = shape_of(types[fname])
                if sort is None:
                    sort = _sort_name(types[fname])
            if role is None:
                # A field holding plain data is an attr; anything holding nodes
                # is a child. Without `_field_types` the sort is unknown, and
                # `child` is the answer that keeps traversal complete.
                role = ATTR if sort in {"str", "int", "object", "bool"} else CHILD
            fields.append(
                Field(name=fname, role=role, shape=shape, sort=sort, when=when)
            )
        builder.production(
            prod_name,
            *fields,
            traits=("scope",) if prod_name in SCOPES else (),
            cls=cls,
        )
    return builder.build()


def _sort_name(annotation: object) -> str:
    text = str(annotation)
    for prefix in ("list[", "ast."):
        text = text.replace(prefix, "")
    return (
        text
        .replace("]", "")
        .replace(" | None", "")
        .replace("<class '", "")
        .replace("'>", "")
        .strip()
    )


#: Built once. Grammars are immutable.
PY = build()
