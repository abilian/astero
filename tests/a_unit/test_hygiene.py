"""Substitution and renaming, driven by the grammar's roles.

The two defects this exists to make unwritable are both in the corpus. p2w's
inliner substituted at every `Name`, so it wrote `[99 for 99 in [7, 8]]`.
latexify's renamer enumerated identifier slots by hand and missed four of them.
"""

from __future__ import annotations

import ast

import pytest

from astero.python import PY, VARS
from astero.python.hygiene import (
    CaptureError,
    Fresh,
    all_names,
    bound_here,
    free_names,
    rename,
    substitute,
)


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _sub(source: str, mapping: dict[str, str], **kwargs) -> str:
    out = substitute(
        ast.parse(source),
        {name: _expr(value) for name, value in mapping.items()},
        PY,
        VARS,
        **kwargs,
    )
    return ast.unparse(out)


# ----------------------------------------------------------- use versus bind


def test_a_use_is_replaced() -> None:
    assert _sub("return x + 1", {"x": "3"}) == "return 3 + 1"


def test_an_attribute_target_reads_the_name_it_writes_through() -> None:
    """`b.f = v` binds nothing. `b` is a use, even in a binding position."""
    assert _sub("b.f = v", {"b": "obj"}) == "obj.f = v"


def test_a_subscript_target_reads_both_its_parts() -> None:
    assert _sub("b[i] = v", {"b": "xs", "i": "k"}) == "xs[k] = v"


def test_a_binding_occurrence_is_not_replaced() -> None:
    """The defect that produced `[99 for 99 in [7, 8]]`."""
    tree = ast.parse("t = [y for y in ys]")
    out = substitute(tree, {"ys": _expr("[7, 8]")}, PY, VARS)
    assert ast.unparse(out) == "t = [y for y in [7, 8]]"


def test_substituting_for_a_bound_name_is_refused() -> None:
    with pytest.raises(CaptureError, match="binds"):
        _sub("t = [x for x in [7, 8]]", {"x": "99"})
    with pytest.raises(CaptureError, match="binds"):
        _sub("x = x + 1\nreturn x", {"x": "3"})


# ------------------------------------------------------------------- capture


def test_capture_is_refused_without_a_name_supply() -> None:
    with pytest.raises(CaptureError, match="capture"):
        _sub("def g(y):\n    return y + z", {"z": "y"})


def test_capture_is_repaired_by_renaming_the_binder() -> None:
    out = _sub("def g(y):\n    return y + z", {"z": "y"}, fresh=Fresh("_h"))
    assert out == "def g(_h1):\n    return _h1 + y"


def test_a_replacement_is_copied_per_occurrence() -> None:
    tree = ast.parse("return x + x")
    out = substitute(tree, {"x": _expr("f()")}, PY, VARS)
    calls = [n for n in ast.walk(out) if isinstance(n, ast.Call)]
    assert len(calls) == 2
    assert calls[0] is not calls[1]


def test_the_input_is_not_mutated() -> None:
    tree = ast.parse("return x")
    substitute(tree, {"x": _expr("1")}, PY, VARS)
    assert ast.unparse(tree) == "return x"


# ------------------------------------------------------------------ renaming


def test_rename_reaches_every_identifier_slot() -> None:
    """The four latexify missed, and the ones it did not."""
    source = (
        "def f(a, *args, k=1, **kw):\n"
        "    b = lambda p: p + a\n"
        "    try:\n"
        "        import a as a2\n"
        "    except ValueError as a3:\n"
        "        pass\n"
        "    return args, kw, b\n"
    )
    tree = ast.parse(source)
    mapping = {name: name.upper() for name in ("a", "args", "kw", "p", "a3")}
    renamed = rename(tree, mapping, PY, VARS)
    # Ask the grammar which names are present rather than reading the text.
    present = all_names(renamed, PY)
    assert set(mapping.values()) <= present
    assert not (set(mapping) & present - {"a"}), "an old name survived"
    # `a` survives only as the module path of `import a as a2`, which names a
    # module and not the variable being renamed.
    assert "import a as a2" in ast.unparse(renamed)


def test_rename_touches_both_the_binding_and_its_uses() -> None:
    tree = ast.parse("def f(x):\n    return x + 1")
    out = ast.unparse(rename(tree, {"x": "y"}, PY, VARS))
    assert out == "def f(y):\n    return y + 1"


# --------------------------------------------------------------------- names


def test_free_and_bound_names() -> None:
    tree = ast.parse("def g(y):\n    return y + z")
    assert bound_here(tree, PY, VARS) == {"g", "y"}
    assert free_names(tree, PY, VARS) == {"z"}
    assert all_names(tree, PY) == {"g", "y", "z"}


def test_fresh_avoids_names_already_present() -> None:
    tree = ast.parse("_h1 = 1")
    supply = Fresh.avoiding(tree, PY, prefix="_h")
    assert supply() == "_h2"
    assert supply() == "_h3"


def test_fresh_never_repeats() -> None:
    supply = Fresh("_t")
    assert len({supply() for _ in range(50)}) == 50


# ---------------------------------------------------------------- the tables


def test_the_identifier_slots_come_from_the_grammar() -> None:
    """Not a list in this module. The one in latexify was missing four."""
    slots = PY.ident_slots()
    for production, field_name in [
        ("Name", "id"),
        ("arg", "arg"),
        ("FunctionDef", "name"),
        ("ExceptHandler", "name"),
        ("alias", "asname"),
        ("Global", "names"),
    ]:
        assert field_name in slots.get(production, ()), (production, field_name)


def test_a_sequence_of_identifiers_renames_elementwise() -> None:
    """`Global.names` holds a list of strings, not a node."""
    field = PY["Global"].field("names")
    assert field is not None
    assert field.sort == "ident"
    tree = ast.parse("def f():\n    global a, b\n    return a")
    out = ast.unparse(rename(tree, {"a": "c"}, PY, VARS))
    assert "global c, b" in out


# -------------------------------------------------------------------- scopes


def _sub_scoped(source: str, mapping: dict[str, str], **kwargs) -> str:
    from astero.python import BINDING_SCOPES

    return _sub(source, mapping, scopes=BINDING_SCOPES, **kwargs)


def test_an_inner_scope_hides_the_name_instead_of_refusing() -> None:
    """A comprehension binds its own `x`, so the outer one is free after it."""
    source = "t = [x for x in [7, 8]]\ny = x"
    with pytest.raises(CaptureError):
        _sub(source, {"x": "99"})
    assert _sub_scoped(source, {"x": "99"}) == "t = [x for x in [7, 8]]\ny = 99"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("f = lambda x: x + 1\ny = x", "f = lambda x: x + 1\ny = 99"),
        ("def g(x):\n    return x\ny = x", "def g(x):\n    return x\ny = 99"),
        ("t = {x for x in s}\ny = x", "t = {x for x in s}\ny = 99"),
        ("t = {x: 1 for x in s}\ny = x", "t = {x: 1 for x in s}\ny = 99"),
    ],
)
def test_every_binding_region_hides_its_own_name(source: str, expected: str) -> None:
    assert _sub_scoped(source, {"x": "99"}) == expected


def test_a_nested_scope_hides_a_name_only_inside_itself() -> None:
    """The comprehension binds `v` and the lambda around it does not, so the
    lambda's own `v` is free. Counting the comprehension's binding as the
    lambda's left that `v` unreplaced."""
    source = "f = lambda: [v for v in xs] + [v]"
    assert _sub_scoped(source, {"v": "99"}) == "f = lambda: [v for v in xs] + [99]"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("v + sum(v * z for v in xs)", "v + sum((_h1 * v for _h1 in xs))"),
        (
            "def g(v):\n    return v + z\nw = v",
            "def g(_h1):\n    return _h1 + v\nw = v",
        ),
    ],
)
def test_a_repair_renames_only_where_the_captor_binds(
    source: str, expected: str
) -> None:
    """A `v` outside the captor's scope is free, like the `v` coming in, and
    renaming it too cut it loose: `_h1 + sum(_h1 * v for _h1 in xs)`."""
    assert _sub_scoped(source, {"z": "v"}, fresh=Fresh("_h")) == expected


def test_scopes_find_a_name_free_beside_its_own_binding() -> None:
    """The first `t` is free and the generator's is not. Without a scope table
    the expression counts as one scope, where `t` is bound everywhere."""
    from astero.python import BINDING_SCOPES

    expr = _expr("t + sum(t for t in xs)")
    assert free_names(expr, PY, VARS) == {"sum", "xs"}
    assert free_names(expr, PY, VARS, scopes=BINDING_SCOPES) == {"t", "sum", "xs"}


def test_a_name_free_beside_its_own_binding_is_not_captured() -> None:
    """Counting that `t` as bound let `g`'s parameter capture it."""
    out = _sub_scoped(
        "def g(t):\n    return t + z",
        {"z": "t + sum(t for t in xs)"},
        fresh=Fresh("_h"),
    )
    assert out == "def g(_h1):\n    return _h1 + (t + sum((t for t in xs)))"


def test_a_real_rebinding_is_still_refused() -> None:
    """Shadowing hides a name. Assignment changes it, which is different."""
    with pytest.raises(CaptureError, match="binds"):
        _sub_scoped("x = 1\ny = x", {"x": "99"})


def test_a_decorator_is_outside_the_scope_it_decorates() -> None:
    """`inside` is per field, so a decorator sees the enclosing binding."""
    source = "@x\ndef g(x):\n    return x\n"
    assert _sub_scoped(source, {"x": "d"}) == "@d\ndef g(x):\n    return x"


def test_comprehensions_bind_whatever_symtable_calls_them() -> None:
    """PEP 709 stopped a comprehension being a block; it still binds.

    `SCOPES` answers the block question and changes at 3.12. `BINDING_SCOPES`
    answers the binding question and does not.
    """
    from astero.python import BINDING_SCOPES, SCOPES

    for production in ("ListComp", "SetComp", "DictComp"):
        assert production in BINDING_SCOPES
    assert set(SCOPES) <= set(BINDING_SCOPES)
    q = "outer"
    assert [q * 2 for q in range(3)] == [0, 2, 4]
    assert q == "outer", "the iteration variable leaked, which it never does"


def test_rename_stays_inside_its_namespace() -> None:
    """`Attribute.attr` and `keyword.arg` are identifier slots in another one.

    Renaming the variable `foo` must not rewrite `x.foo` into a different
    attribute, nor `f(foo=1)` into a call with a different keyword.
    """
    for source in ("y = x.foo", "f(foo=1)", "obj.foo = obj.foo + 1"):
        tree = ast.parse(source)
        assert ast.unparse(rename(tree, {"foo": "R"}, PY, VARS)) == source

    tree = ast.parse("foo = 1")
    assert ast.unparse(rename(tree, {"foo": "R"}, PY, VARS)) == "R = 1"


def test_the_namespace_split_is_in_the_grammar_not_here() -> None:
    everywhere = PY.ident_slots()
    variables = PY.ident_slots(VARS)
    assert "attr" in everywhere["Attribute"]
    assert "Attribute" not in variables
    assert "keyword" not in variables
    assert "id" in variables["Name"]


def test_a_bare_name_is_substituted() -> None:
    """The root has no parent to be swapped by, and used to be skipped.

    Found by prescrypt-ng lowering `[n for n, _ in pairs]` onto a closure: the
    element expression is the single name `n`, and substituting a subscript for
    it returned `n` unchanged. Silent, and the generated JavaScript referred to
    a variable that no longer existed.
    """
    body = ast.parse("n", mode="eval").body
    out = substitute(body, {"n": ast.parse("t[0]", mode="eval").body}, PY, VARS)
    assert ast.unparse(out) == "t[0]"


def test_a_bare_name_that_is_not_in_the_mapping_is_left_alone() -> None:
    body = ast.parse("other", mode="eval").body
    out = substitute(body, {"n": ast.parse("t[0]", mode="eval").body}, PY, VARS)
    assert ast.unparse(out) == "other"


def test_a_global_declaration_binds_nothing_where_it_is_written() -> None:
    """`g` is the module's in `f`: a use of it is substitutable, and an
    assignment to it rebinds the name being substituted. Counting an assigned
    `g` as `f`'s own missed the rebinding and skipped every use beside it."""
    reading = "def f():\n    global g\n    return g"
    assert _sub_scoped(reading, {"g": "99"}) == "def f():\n    global g\n    return 99"
    with pytest.raises(CaptureError, match="binds"):
        _sub_scoped("def f():\n    global g\n    g = 1", {"g": "99"})


def test_a_class_body_does_not_shadow_its_methods() -> None:
    """The method's `x` is the module's: class names are not visible in it."""
    source = "class C:\n    x = 1\n\n    def m(self):\n        return x"
    out = _sub_scoped(source, {"x": "99"})
    assert out.endswith("return 99")
