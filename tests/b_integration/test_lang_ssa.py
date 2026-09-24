"""A3, A4, A5: the declared SSA grammar against postpile's own account of its IR.

The load-bearing claim of the design is that one notation declares both a tree
AST and a flat SSA IR. These are the checks that can falsify it.

**A3's oracle changed on 2026-08-13, because postpile stopped writing the table
it used to read.** `_OPERAND_FIELDS` was a hand-written row per instruction;
postpile now declares roles in `compiler/grammar.py` and derives that table from
them. So A3 reads the *declaration* and applies the same rule postpile applies
to it, which is a stronger check than the one it replaced: `lang_ssa.py` is a
hand transcription, and it is now held to a declaration rather than to another
transcription. A4 and A5 still read code, because `_operands()` and `_pure_key`
are still written out.

The two grammars model one thing differently and agree anyway, which is worth
saying: astero's transcription puts `AssignValue.target` in a `slots`
namespace, postpile's declaration keeps it in `vals` under a `Present`/`Absent`
condition. Both keep it out of the operand set, by different routes.

postpile is read, never imported: everything is extracted from its source with
`ast`, so this needs a checkout on disk and nothing installed. Point
`POSTPILE_SRC` at one, or leave it beside astero.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from postpile_ir.grammar import SSA, VALS

from astero.grammar import Kind

_CANDIDATES = [
    Path(os.environ["POSTPILE_SRC"]) if os.environ.get("POSTPILE_SRC") else None,
    # The sandbox copy comes first. There is often a second checkout beside
    # astero, and reading that one while editing this one validates a tree
    # nobody is changing.
    Path(__file__).resolve().parents[2] / "sandbox" / "postpile",
    Path(__file__).resolve().parents[3] / "postpile",
    Path.home() / "projects" / "compilers" / "postpile",
]


def _postpile() -> Path:
    for root in _CANDIDATES:
        if root and (root / "src/postpile/compiler/ir.py").exists():
            return root
    pytest.skip("no postpile checkout found; set POSTPILE_SRC")
    raise AssertionError  # unreachable, satisfies the type checker


def _module(rel: str) -> ast.Module:
    return ast.parse((_postpile() / rel).read_text(encoding="utf-8"))


def _module_dict(tree: ast.Module, name: str) -> ast.Dict:
    """The `name = {...}` literal at module level, as source."""
    for node in tree.body:
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        value = getattr(node, "value", None)
        if target == name and isinstance(value, ast.Dict):
            return value
    raise AssertionError(f"{name} not found in postpile's source")


def _rewritable_from_roles() -> dict[str, tuple[str, ...]]:
    """postpile's operand table, derived from its `ROLES` the way postpile does.

    "Reads a value and, under no condition, introduces one" — which is what
    keeps `AssignValue.target` out, since a slot that can be a definition names
    storage. Read out of the source rather than imported, so this needs a
    checkout and not an installed postpile.
    """
    roles = _module_dict(_module("src/postpile/compiler/grammar.py"), "ROLES")
    out: dict[str, tuple[str, ...]] = {}
    for prod, spec in zip(roles.keys, roles.values, strict=True):
        assert isinstance(prod, ast.Constant)
        assert isinstance(spec, ast.Dict)
        fields = []
        for field, role in zip(spec.keys, spec.values, strict=True):
            assert isinstance(field, ast.Constant)
            text = ast.unparse(role)
            if "uses(" in text and "defines(" not in text:
                assert isinstance(field.value, str)
                fields.append(field.value)
        if fields:
            assert isinstance(prod, ast.Constant)
            assert isinstance(prod.value, str)
            out[prod.value] = tuple(fields)
    return out


def _terminator_positions() -> dict[str, tuple[str, ...]]:
    """The operand fixups `cse()` performs on terminators, by a separate `match`.

    That this is a second, hand-written traversal is the point: the grammar
    answers for instructions and terminators with one query.
    """
    tree = _module("src/postpile/compiler/backends/qbe/passes.py")
    found: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "cse":
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Match):
                continue
            for case in sub.cases:
                pattern = ast.unparse(case.pattern)
                assigned = tuple(
                    t.attr
                    for stmt in case.body
                    if isinstance(stmt, ast.Assign)
                    for t in stmt.targets
                    if isinstance(t, ast.Attribute)
                )
                if assigned:
                    cls = pattern.split("(")[0].strip()
                    found[cls] = assigned
    return found


def _pure_productions() -> set[str]:
    """The instructions `_pure_key` returns a key for. A5's oracle."""
    tree = _module("src/postpile/compiler/backends/qbe/passes.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_pure_key":
            return {
                ast.unparse(case.pattern).split("(")[0].strip()
                for case in next(
                    s for s in ast.walk(node) if isinstance(s, ast.Match)
                ).cases
                if not ast.unparse(case.pattern).startswith("_")
            }
    raise AssertionError("_pure_key not found")


def _mentions_value(annotation: ast.expr) -> bool:
    """Whether an annotation names the `Value` type itself.

    A substring test would take `ConstValue` too, which is a literal payload
    rather than an SSA value. `_operands()` gets this right by asking
    `isinstance`; reading the source has to ask the same question of the tokens.
    """
    return any(
        isinstance(n, ast.Name) and n.id == "Value" for n in ast.walk(annotation)
    )


def _value_typed_fields() -> dict[str, tuple[str, ...]]:
    """What `_operands()` collects by reflection: Value-typed fields but `result`."""
    tree = _module("src/postpile/compiler/ir.py")
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields = tuple(
            s.target.id
            for s in node.body
            if isinstance(s, ast.AnnAssign)
            and isinstance(s.target, ast.Name)
            and _mentions_value(s.annotation)
            and s.target.id != "result"
        )
        if fields:
            out[node.name] = fields
    return out


def _derived(kinds: tuple[Kind, ...]) -> dict[str, tuple[str, ...]]:
    return {
        name: fields
        for name, fields in SSA.positions(kinds, VALS).items()
        if name in SSA
    }


def test_a3_operand_positions_match_postpiles_declaration() -> None:
    """A3: derived `use(vals)` == what postpile's roles say, plus the terminators.

    The terminators are still a `match` inside `cse()`, and that they need a
    second traversal at all is the point: the grammar answers for instructions
    and terminators with one query.
    """
    oracle = _rewritable_from_roles()
    oracle.update(_terminator_positions())

    derived = _derived((Kind.USE, Kind.DEFUSE))
    assert derived == oracle, (
        "declared operand positions disagree with postpile's:\n"
        f"  only in grammar: { {k: v for k, v in derived.items() if oracle.get(k) != v} }\n"
        f"  only in postpile: { {k: v for k, v in oracle.items() if derived.get(k) != v} }"
    )


def test_a4_reflection_over_approximates_by_exactly_the_definitions() -> None:
    """A4: postpile's two mechanisms differ, and the grammar says where.

    `_operands()` collects every Value-typed field but `result`, so it also
    sweeps up `AssignValue.target`, which the operand table deliberately omits
    because it names a mutable slot. Reflection cannot tell a use from a
    definition; a declared role can. `_operands()` is still written out in
    postpile, because for its one caller the over-approximation is safe: it
    asks whether a loop counter is *mentioned* anywhere, and a definition of
    the counter disqualifies the loop just as a use does.
    """
    reflection = _value_typed_fields()
    uses = _derived((Kind.USE, Kind.DEFUSE))
    defs = SSA.positions((Kind.DEF, Kind.DEFUSE))

    for name, fields in reflection.items():
        if name not in SSA:
            continue
        expected = set(uses.get(name, ())) | {
            f for f in defs.get(name, ()) if f != "result"
        }
        assert set(fields) == expected, (
            f"{name}: reflection {fields} vs grammar {expected}"
        )

    slot_positions = SSA.positions(Kind.DEF, "slots")
    assert slot_positions == {"AssignValue": ("target",)}
    assert "target" in reflection["AssignValue"], "reflection sweeps the slot in"
    assert "target" not in uses.get("AssignValue", ()), "the grammar keeps it out"


def test_a5_purity_matches_the_hand_written_enumeration() -> None:
    """A5: the `pure` trait == the set `_pure_key` returns a key for."""
    assert SSA.with_trait("pure") == _pure_productions()


def test_the_ssa_grammar_is_well_formed() -> None:
    assert SSA.check() == []
