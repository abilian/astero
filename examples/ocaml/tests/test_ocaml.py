"""The caml-prépa example: a language whose binders are trees.

PL/0 asks whether astero assumed a Python syntax tree. This one asks a
narrower question: whether the derivations hold for a language whose binding
positions are *patterns* rather than single identifier fields, and which
keeps five namespaces apart rather than two.

Writing it produced one result, and the tests below hold it: the difference
between `let` and `let rec` is not expressible as a `Scope` layer, because
the two fields that would have to differ belong to a grandchild of the
production that opens the scope. `test_residual_*` are the record.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Any

import pytest

EXAMPLE = Path(__file__).resolve().parents[1]
SOURCE = EXAMPLE / "src/ocaml"
#: The caml-prépa site has two editions; astero's own documentation has a
#: chapter about this compiler. All three quote it, and all three are checked.
DOCS = EXAMPLE / "docs"
EDITIONS = ("en", "fr")
DOC_ROOTS = (
    *(DOCS / lang / "src" for lang in EDITIONS),
    EXAMPLE.parents[1] / "docs/src/caml",
)
#: Every programme under `corpus/`, including the `simonet/` set, which
#: is a directory of its own because it comes from one place.
CORPUS = sorted((EXAMPLE / "corpus").rglob("*.ml"))

#: What the `ocaml` fixture hands a test. `Any` because `parse` is a
#: function and the rest are modules, as in `test_pl0.py`.
Modules = dict[str, Any]


@pytest.fixture(scope="module")
def ocaml() -> Modules:
    """The example's modules.

    A plain import: every example is a package under its own `src/`, so a
    module here is `ocaml.parser` and cannot shadow anything standard.
    `pythonpath = ["src"]` in this project's `pyproject.toml` is what puts
    the package in reach.
    """
    from ocaml import syntax
    from ocaml.front import lexer, parser
    from ocaml.middle import analyze, grammar

    return {
        "analyze": analyze,
        "grammar": grammar,
        "lexer": lexer,
        "parse": parser.parse,
        "parser": parser,
        "syntax": syntax,
    }


# ------------------------------------------------------------------- lexing


def test_no_module_shadows_a_standard_library_one(ocaml: Modules) -> None:
    """A package cannot shadow a standard module, and this holds it that way.

    `infer.py` was `types.py`, and while these sources sat at the top of a
    directory that reached `sys.path`, importing anything from here broke
    `dataclasses`, which imports `types`. The `src/ocaml/` layout is the
    real fix; this is what keeps a module from being named as if it were
    not.
    """
    import sys

    found = {path.stem for path in SOURCE.rglob("*.py")}
    found |= {path.stem for path in (EXAMPLE / "web").glob("*.py")}
    assert found & sys.stdlib_module_names == set()


def test_a_character_literal_is_not_a_type_variable(ocaml: Modules) -> None:
    kinds = [t.kind for t in ocaml["lexer"].tokenize("'a' 'a")]
    assert kinds == ["char", "tyvar", "eof"]


def test_comments_nest(ocaml: Modules) -> None:
    tokens = ocaml["lexer"].tokenize("1 (* a (* b *) c *) 2")
    assert [t.text for t in tokens] == ["1", "2", ""]


def test_an_unterminated_comment_is_an_error(ocaml: Modules) -> None:
    with pytest.raises(SyntaxError):
        ocaml["lexer"].tokenize("1 (* a (* b *)")


# ------------------------------------------------------------------ parsing


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_parses(ocaml: Modules, path: Path) -> None:
    tree = ocaml["parse"](path.read_text(encoding="utf-8"))
    assert tree.items


#: Groupings PEG gets right by construction and an LR generator needs a
#: precedence declaration for. `specification.md`, *Precedence*, is the table.
GROUPINGS = [
    ("1 + 2 * 3", "1 + (2 * 3)"),
    ("1 + 2 :: l @ m", "((1 + 2) :: l) @ m"),
    ("- x ** 2", "(- x) ** 2"),
    ("a - b - c", "(a - b) - c"),
    ("a ** b ** c", "a ** (b ** c)"),
    ("f -1", "f - 1"),
    ("if a then b; c", "(if a then b); c"),
    ("if a then if b then c else d", "if a then (if b then c else d)"),
    ("let x = 1 in a; b", "let x = 1 in (a; b)"),
    ("a; let x = 1 in b", "a; (let x = 1 in b)"),
    ("match n with 0 -> a; b | _ -> c", "match n with 0 -> (a; b) | _ -> c"),
    ("fun x -> a; b", "fun x -> (a; b)"),
]


@pytest.mark.parametrize(("terse", "explicit"), GROUPINGS)
def test_parenthesising_it_changes_nothing(
    ocaml: Modules, terse: str, explicit: str
) -> None:
    """The two spellings build the same tree, so the grouping is the stated one."""
    assert ocaml["parse"](terse) == ocaml["parse"](explicit)


def test_an_operator_can_be_a_value(ocaml: Modules) -> None:
    tree = ocaml["parse"]("let sum = List.fold_left ( + ) 0")
    call = tree.items[0].bindings[0].value
    assert [type(a).__name__ for a in call.args] == ["Var", "Int"]
    assert call.args[0].name == "+"


def test_arrow_left_needs_a_field_or_an_element(ocaml: Modules) -> None:
    ocaml["parse"]("let f a = a.(0) <- 1")
    ocaml["parse"]("let f r = r.x <- 1")
    with pytest.raises(SyntaxError):
        ocaml["parse"]("let f x = x <- 1")


# -------------------------------------------------------------------- spans


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_every_node_knows_where_it_came_from(ocaml: Modules, path: Path) -> None:
    """The stepper points at source, so every parsed node needs a span."""
    from astero.scopes import walk

    source = path.read_text(encoding="utf-8")
    tree = ocaml["parse"](source)
    for node in walk(tree, ocaml["grammar"].OCAML):
        assert node.span is not None, type(node).__name__
        start, end = node.span
        assert 0 <= start <= end <= len(source), type(node).__name__
        assert source[start:end].strip(), type(node).__name__


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_a_span_contains_the_spans_below_it(ocaml: Modules, path: Path) -> None:
    """A child came from inside its parent's text, or one of them is wrong.

    The oracle for positions, and the one that catches an off-by-one or a
    token index taken from the wrong end. Printing cannot check this: the
    printer discards layout, which is what makes `span` `compare=False`.
    """
    declared = ocaml["grammar"].OCAML
    tree = ocaml["parse"](path.read_text(encoding="utf-8"))

    def check(node: Any) -> None:
        for field in declared.children(type(node).__name__):
            held = getattr(node, field.name)
            for child in held if isinstance(held, list) else [held]:
                if child is None or not hasattr(child, "span"):
                    continue
                assert node.span[0] <= child.span[0], f"{node} / {child}"
                assert child.span[1] <= node.span[1], f"{node} / {child}"
                check(child)

    check(tree)


def test_a_span_is_data_and_not_a_child(ocaml: Modules) -> None:
    """`Span` has to be named as plain data, or traversal descends into it.

    `from_dataclasses` makes an unroled field of an unknown sort a `child`,
    which is the answer that keeps traversal complete. `Span` is an alias
    for a pair of offsets, so without `data_sorts` naming it every walk in
    the compiler would try to enter a tuple. Nothing failed when the field
    was added, because nothing filled it yet.
    """
    declared = ocaml["grammar"].OCAML
    for name in declared.concrete():
        assert "span" not in {f.name for f in declared.children(name)}, name


# ---------------------------------------------------------------- the grammar


def test_every_identifier_field_carries_a_role(ocaml: Modules) -> None:
    """An `Ident` field with no role would be traversed as a child.

    The check that keeps the declaration total: `from_dataclasses` gives an
    unroled field `child` when its sort is not plain data, and `Ident` is not.
    """
    declared = ocaml["grammar"].OCAML
    unroled = {
        (prod.name, f.name)
        for prod in declared
        for f in prod.fields
        if f.sort == ocaml["grammar"].IDENT and str(f.role) == "child"
    }
    assert unroled == set()


def test_the_five_namespaces_are_separate(ocaml: Modules) -> None:
    g = ocaml["grammar"]
    assert set(g.OCAML.definitions(g.VALS)) == {"PVar", "PAlias"}
    assert set(g.OCAML.definitions(g.CONS)) == {"Variant", "ExnItem"}
    assert set(g.OCAML.operands(g.FIELDS)) == {
        "FieldBind",
        "GetField",
        "SetField",
        "PField",
    }


def test_a_constructor_and_an_exception_share_a_namespace(ocaml: Modules) -> None:
    """OCaml shares it, so the declaration does, and shadowing needs no case."""
    tree = ocaml["parse"]("type t = E  exception E  let x = E")
    assert ocaml["analyze"].unbound(tree) == []


# ---------------------------------------------------------------- resolution


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_resolves(ocaml: Modules, path: Path) -> None:
    assert (
        ocaml["analyze"].unbound(ocaml["parse"](path.read_text(encoding="utf-8"))) == []
    )


UNRESOLVED = [
    ("let x = 1 let y = x + z", "vals"),
    ("type t = A let x = C", "cons"),
    ("type t = { a : int } let g r = r.b", "fields"),
    ("let g (x : nosuch) = x", "types"),
]


@pytest.mark.parametrize(("source", "ns"), UNRESOLVED)
def test_an_undeclared_name_is_reported(ocaml: Modules, source: str, ns: str) -> None:
    problems = ocaml["analyze"].unbound(ocaml["parse"](source))
    assert len(problems) == 1
    assert problems[0].endswith(f"is not declared in {ns}")


NOT_LEAKED = [
    ("let h = fun a -> a  let i = a", "a function's parameter"),
    ("let j = match 1 with q -> q  let k = q", "a match arm's pattern"),
    ("let p = (for i = 0 to 3 do () done); i", "a for loop's index"),
    ("let g = (let z = 1 in z) + z", "a let's binding"),
    ("let f x = x  let g = x", "a definition's parameter"),
]


@pytest.mark.parametrize(("source", "what"), NOT_LEAKED)
def test_a_binder_does_not_escape_its_scope(
    ocaml: Modules, source: str, what: str
) -> None:
    assert ocaml["analyze"].unbound(ocaml["parse"](source)), what


def test_let_rec_sees_itself(ocaml: Modules) -> None:
    source = "let rec fact n = if n = 0 then 1 else n * fact (n - 1)"
    assert ocaml["analyze"].unbound(ocaml["parse"](source)) == []


def test_the_scope_tree_nests(ocaml: Modules) -> None:
    tree = ocaml["parse"]("let rec f x = let y = x in y")
    root = ocaml["analyze"].blocks(tree, ocaml["grammar"].VALS)
    assert root.shape() == ("module", "top", (("binding", "", (("let", "", ()),)),))
    binding = root.children[0]
    assert binding.owns() == {"x"}
    assert binding.children[0].owns() == {"y"}
    assert root.owns() == {"f"}


# ------------------------------------------------------------------ printing
#
# `emit.py` prints a tree back to source, and reparsing it has to give the
# same tree. That is the oracle for the grammar: a rule that groups the
# wrong way survives every hand-written assertion and dies here.


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_round_trips(ocaml: Modules, path: Path) -> None:
    from ocaml.front import emit

    tree = ocaml["parse"](path.read_text(encoding="utf-8"))
    assert ocaml["parse"](emit.unparse(tree)) == tree


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_printing_is_stable(ocaml: Modules, path: Path) -> None:
    """Printing twice gives the same text, so nothing oscillates."""
    from ocaml.front import emit

    once = emit.unparse(ocaml["parse"](path.read_text(encoding="utf-8")))
    assert emit.unparse(ocaml["parse"](once)) == once


#: Sources whose tree survives a round trip only if a bracket is derived.
#: Each one is a place where the printer would otherwise emit text that
#: reparses into something else.
BRACKETED = [
    "let a = if c then (x; y) else z",
    "let a = match n with 0 -> (match m with 1 -> p | _ -> q) | _ -> r",
    "let a = f (g x)",
    "let a = f (-1)",
    "let a = (f x).lbl",
    "let a = !(r.lbl)",
    "let a = (a + b) * c",
    "let a = a :: (b @ c)",
    "let a = (let x = 1 in x) + 2",
    "let a = [ (x; y); z ]",
    "let a = ((p, q), r)",
    "let a = (fun x -> x) 1",
    "let a = (function 0 -> p | _ -> q) 1",
    "let a = - (x ** y)",
    "let a = (r.f <- 1); g",
    "type t = (int -> int) list",
    "type t = (int * int) option",
    "let f (p : int option) = match p with Some (x) -> x | None -> 0",
]


@pytest.mark.parametrize("source", BRACKETED)
def test_a_bracket_that_carries_meaning_survives(ocaml: Modules, source: str) -> None:
    from ocaml.front import emit

    tree = ocaml["parse"](source)
    assert ocaml["parse"](emit.unparse(tree)) == tree


def test_the_printer_handles_every_production(ocaml: Modules) -> None:
    """The obligation `astero.coverage` states, over a `match`-based printer.

    A production added to `syntax.py` and left out of `emit.py` fails here
    rather than at the first program that happens to use it.
    """
    from astero.coverage import Coverage, match_arms
    from ocaml.front import emit

    found = Coverage(
        handled=match_arms(
            emit.expr_doc,
            emit.pat_doc,
            emit.type_doc,
            emit.item_doc,
            emit.rhs_doc,
        ),
        expected=ocaml["grammar"].OCAML.concrete(),
        accounted={
            "printed by the production that owns it": frozenset({
                "Binding",
                "Case",
                "FieldBind",
                "FieldDef",
                "PField",
                "Structure",
                "TypeDef",
                "Variant",
            })
        },
    )
    assert not found.missing, found.explain()
    assert not found.absent, found.explain()
    assert not found.redundant, found.explain()


def test_the_corpus_reaches_every_production(ocaml: Modules) -> None:
    """The corpus is the language, not a sample of it.

    Equality rather than a threshold: a production is either exercised by a
    programme somebody would write, or it does not belong in the grammar.
    """
    from astero.scopes import walk

    declared = ocaml["grammar"].OCAML
    seen: set[str] = set()
    for path in CORPUS:
        tree = ocaml["parse"](path.read_text(encoding="utf-8"))
        seen |= {type(node).__name__ for node in walk(tree, declared)}
    assert declared.concrete() - seen == set()


# --------------------------------------------------------------- the corpus
#
# `corpus/` is flat except for two sets: `simonet/`, twenty-three programmes
# written from one series of exercises, and `grimaud/`, nineteen copied from
# the solutions published with a textbook. Every test above applies to them
# because `CORPUS` recurses; the tests below hold each set together.

#: The programmes taken from Vincent Simonet's exercise series.
SIMONET = sorted((EXAMPLE / "corpus/simonet").glob("*.ml"))

#: The programmes copied from the solutions of *Informatique MPI*.
GRIMAUD = sorted((EXAMPLE / "corpus/grimaud").glob("*.ml"))


def test_every_corpus_name_is_unique(ocaml: Modules) -> None:
    """The bundle flattens the tree, so two `tri.ml` would be one file.

    `web/build.py` writes `corpus/<name>` whatever directory a programme
    sits in, because the page lists one directory. That is fine only while
    the names do not collide, and this is what says so.
    """
    names = [path.name for path in CORPUS]
    assert sorted(names) == sorted(set(names))


def test_every_simonet_programme_credits_its_source(ocaml: Modules) -> None:
    """The exercises are somebody's, and each programme says whose.

    The statements are published under the GNU FDL, so what is here is the
    algorithm rewritten rather than the text copied. That distinction is
    only honest if the reader can find the original, which is what the
    header comment is for.
    """
    assert len(SIMONET) == 23
    for path in SIMONET:
        # The comment wraps, so the name can straddle a line break.
        head = " ".join(path.read_text(encoding="utf-8")[:400].split())
        assert "Vincent Simonet" in head, path.name
        assert "TP" in head, path.name


@pytest.mark.parametrize("paths", [SIMONET, GRIMAUD], ids=["simonet", "grimaud"])
def test_each_readme_lists_every_programme(ocaml: Modules, paths: list[Path]) -> None:
    """The index and the directory say the same thing, in both directions."""
    readme = (paths[0].parent / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `([a-z_0-9]+\.ml)`", readme, re.MULTILINE))
    assert listed == {path.name for path in paths}


def test_every_grimaud_programme_says_where_it_came_from(ocaml: Modules) -> None:
    """Copied under the GPL, so each file names its source and its changes.

    The header gives the repository, the commit and the path of every file
    it was made from, and then either says the rest is unchanged or lists
    what was. The licence travels with the files, in `LICENSE`.
    """
    assert len(GRIMAUD) == 19
    assert (
        (EXAMPLE / "corpus/grimaud/LICENSE")
        .read_text(encoding="utf-8")
        .strip()
        .startswith("GNU GENERAL PUBLIC LICENSE")
    )
    for path in GRIMAUD:
        head = path.read_text(encoding="utf-8").split("*)", 1)[0]
        assert "Grimaud and Gilles Grimaud" in head, path.name
        assert "https://github.com/Informatique-MPI/" in head, path.name
        assert re.search(r"at commit [0-9a-f]{12}:", head), path.name
        assert "GPL-3.0" in head, path.name
        assert ("Unchanged below this comment." in head) != ("Changed:" in head), (
            path.name
        )


# ----------------------------------------------------------------- residuals
#
# Two facts the model gets wrong, asserted so a change to astero that fixes
# either one fails here and gets noticed rather than passing silently.


def test_residual_a_let_sees_the_name_it_binds(ocaml: Modules) -> None:
    """OCaml rejects this: `let` is not `let rec`, so the `z` on the right
    is the outer one, and there is none. `README.md`, *Two residuals*."""
    assert ocaml["analyze"].unbound(ocaml["parse"]("let g = let z = z in z")) == []


def test_a_type_variable_declares_itself_and_a_declaration_checks_it(
    ocaml: Modules,
) -> None:
    """`TVar.name` is `defuse`, so the resolver accepts every `'a`; OCaml's
    rule for a declaration is the checker's to hold. `specification.md`, *Names*."""
    from ocaml.middle.infer import signature
    from ocaml.middle.unify import TypingError

    source = "type 'a box = { it : 'a }  type pair = { fst_ : 'a }"
    assert ocaml["analyze"].unbound(ocaml["parse"](source)) == []
    with pytest.raises(TypingError, match="unbound in this type declaration"):
        signature(ocaml["parse"](source))
    annotated = "let first (l : 'a list) = List.hd l"
    assert ocaml["analyze"].unbound(ocaml["parse"](annotated)) == []
    assert signature(ocaml["parse"](annotated)) == ["val first : 'a list -> 'a"]


# --------------------------------------------------------------- interpreting


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_runs(ocaml: Modules, path: Path, capsys: Any) -> None:
    """Each programme prints what its `.expected` file says.

    A pinned regression, not an independent oracle. The independent one is
    `ocaml` itself, in `test_the_reference_compiler_agrees` below, which
    skips where no compiler is installed.
    """
    from ocaml.back.interpret import run_source

    run_source(path.read_text(encoding="utf-8"))
    expected = path.with_suffix(".expected").read_text(encoding="utf-8")
    assert capsys.readouterr().out == expected


def test_the_reference_compiler_agrees(ocaml: Modules) -> None:
    """`ocaml` prints what the interpreter prints, over the whole corpus."""
    from ocaml import oracle

    if not oracle.available():
        pytest.skip("no `ocaml` on PATH")
    for path in CORPUS:
        expected = path.with_suffix(".expected").read_text(encoding="utf-8")
        assert oracle.reference_output(path) == expected, path.name


def test_the_interpreter_handles_every_production(ocaml: Modules) -> None:
    """The same obligation the printer carries, over the other dispatch."""
    from astero.coverage import Coverage, match_arms
    from ocaml.back import interpret

    found = Coverage(
        handled=match_arms(
            interpret._eval_expr, interpret.match_pattern, interpret.run_item
        ),
        expected=ocaml["grammar"].OCAML.concrete(),
        accounted={
            "structure, not a value": frozenset({
                "Binding",
                "Case",
                "FieldBind",
                "FieldDef",
                "PField",
                "Structure",
                "TypeDef",
                "Variant",
                "Variants",
                "RecordDef",
                "AliasDef",
                "TVar",
                "TCon",
                "TFun",
                "TTuple",
            })
        },
    )
    assert not found.missing, found.explain()
    assert not found.absent, found.explain()
    assert not found.redundant, found.explain()


#: Places the semantics differ from Python's and match OCaml's. Each one is
#: a defect waiting to happen in a back end that reaches for the host
#: operator, so each is asserted rather than assumed.
ARITHMETIC = [
    ("(-7) / 2", -3),  # OCaml truncates towards zero; Python floors to -4
    ("7 / (-2)", -3),
    ("(-7) mod 2", -1),  # the remainder takes the dividend's sign
    ("7 mod (-2)", 1),
    ("1 lsl 10", 1024),
    ("(-8) asr 1", -4),
]


@pytest.mark.parametrize(("source", "expected"), ARITHMETIC)
def test_integer_arithmetic_is_ocamls(
    ocaml: Modules, source: str, expected: int
) -> None:
    from ocaml.back.interpret import run_source

    assert run_source(f"let answer = {source}")["answer"] == expected


def test_division_by_zero_raises_an_ocaml_exception(ocaml: Modules) -> None:
    from ocaml.back.interpret import run_source
    from ocaml.back.runtime import OCamlError

    with pytest.raises(OCamlError) as raised:
        run_source("let a = 1 / 0")
    assert raised.value.value.tag == "Division_by_zero"


def test_float_division_by_zero_does_not(ocaml: Modules) -> None:
    """`1.0 /. 0.0` is `infinity` in OCaml, where Python raises."""
    from ocaml.back.interpret import run_source

    assert run_source("let a = 1.0 /. 0.0")["a"] == float("inf")


def test_comparing_two_functions_raises(ocaml: Modules) -> None:
    """A closure has no structure, and Python's `==` would answer anyway."""
    from ocaml.back.interpret import run_source
    from ocaml.back.runtime import OCamlError

    with pytest.raises(OCamlError) as raised:
        run_source("let a = (fun x -> x) = (fun y -> y)")
    assert raised.value.value.tag == "Invalid_argument"


def test_a_float_prints_as_ocaml_prints_it(ocaml: Modules) -> None:
    from ocaml.back.runtime import show_float

    assert show_float(3.0) == "3."
    assert show_float(0.001) == "0.001"
    assert show_float(float("inf")) == "infinity"


def test_partial_application_needs_no_arity(ocaml: Modules) -> None:
    """Functions are curried, so this falls out rather than being arranged."""
    from ocaml.back.interpret import run_source

    scope = run_source("let add a b = a + b  let inc = add 1  let n = inc 41")
    assert scope["n"] == 42


def test_a_let_rec_closure_sees_the_scope_it_is_being_put_in(
    ocaml: Modules,
) -> None:
    """The mapping is made first and filled after, so mutual recursion works."""
    from ocaml.back.interpret import run_source

    source = """
        let rec even n = if n = 0 then true else odd (n - 1)
        and odd n = if n = 0 then false else even (n - 1)
        let answer = even 10
    """
    assert run_source(source)["answer"] is True


# ------------------------------------------------------------------- typing


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_types(ocaml: Modules, path: Path) -> None:
    """Each programme's inferred signature matches its `.signature` file."""
    from ocaml.middle.infer import signature

    found = signature(ocaml["parse"](path.read_text(encoding="utf-8")))
    expected = path.with_suffix(".signature").read_text(encoding="utf-8").splitlines()
    assert found == expected


def test_the_reference_compiler_agrees_on_types(ocaml: Modules) -> None:
    """`ocamlc -i` infers the same signature, over the whole corpus.

    The oracle section 8 names: the reference implementation's own answer,
    which is the only thing that can tell a wrong inference from a
    consistent one.
    """
    from ocaml import oracle

    if not oracle.typing_available():
        pytest.skip("no `ocamlc` on PATH")
    for path in CORPUS:
        ours = path.with_suffix(".signature").read_text(encoding="utf-8").splitlines()
        assert oracle.reference_signature(path) == ours, path.name


def test_the_type_checker_handles_every_production(ocaml: Modules) -> None:
    from astero.coverage import Coverage, match_arms
    from ocaml.middle import infer

    found = Coverage(
        handled=match_arms(
            infer.infer_expr,
            infer.infer_pattern,
            infer.infer_item,
            infer.literal_type,
            infer.convert,
            infer.is_value,
            infer.declare_rhs,
        ),
        expected=ocaml["grammar"].OCAML.concrete(),
        accounted={
            "reached through the production that owns it": frozenset({
                "Binding",
                "Case",
                "FieldBind",
                "FieldDef",
                "PField",
                "Structure",
                "TypeDef",
                "Variant",
            })
        },
    )
    assert not found.missing, found.explain()
    assert not found.absent, found.explain()
    assert not found.redundant, found.explain()


def test_every_prelude_value_has_a_type(ocaml: Modules) -> None:
    """The runtime supplies a value for each name; this supplies its type.

    Two authored tables mirroring one interface, so the gate is the pattern
    `rewriting.CTX_NODES` uses: assert they still agree.
    """
    from ocaml.back import runtime
    from ocaml.middle import prelude

    assert set(prelude.PRELUDE_TYPES) == set(runtime.ENV)


#: Programmes the checker must reject, and what it must notice about them.
ILL_TYPED = [
    ("let a = 1 + true", "bool"),
    ("let a = 1 +. 2.0", "float"),
    ("let rec f x = f", "cyclic"),
    ('let rec f n = if n = 0 then "" else f true', "bool"),
    ("type t = { a : int }  let g r = r.a <- 1", "not mutable"),
    ("type t = { a : int; b : int }  let g = { a = 1 }", "missing"),
    ("let f = function (Some x) | None -> x", "different names"),
    ("type t = A of int  let g = A", "argument"),
    ("let a = [ 1; true ]", "bool"),
    ("let a = (fun x -> x) 1 2", "int"),
    ("let a = nosuch 1", "unbound value"),
    ("let f (x : nosuch) = x", "unbound type constructor"),
    ("type ('a, 'b) pair = 'a * 'b  let f (x : int pair) = x", "takes 2"),
]


@pytest.mark.parametrize(("source", "says"), ILL_TYPED)
def test_an_ill_typed_programme_is_refused(
    ocaml: Modules, source: str, says: str
) -> None:
    from ocaml.middle.infer import TypingError, signature

    with pytest.raises(TypingError) as raised:
        signature(ocaml["parse"](source))
    assert says in str(raised.value)


#: What generalization does and does not do. Each line is the value
#: restriction or let-polymorphism, and both are easy to get subtly wrong.
SCHEMES = [
    ("let id = fun x -> x", "val id : 'a -> 'a"),
    ("let pair a b = (a, b)", "val pair : 'a -> 'b -> 'a * 'b"),
    ("let swap (a, b) = (b, a)", "val swap : 'a * 'b -> 'b * 'a"),
    # A `ref` is not a value, so its variable stays weak. Generalizing it
    # would let the same cell hold an int and be read as a string.
    ("let r = ref []", "val r : '_weak1 list ref"),
    ("let m = List.map (fun x -> x)", "val m : '_weak1 list -> '_weak1 list"),
    ("let f x : int = x", "val f : int -> int"),
    (
        "let compose f g = fun x -> f (g x)",
        "val compose : ('a -> 'b) -> ('c -> 'a) -> 'c -> 'b",
    ),
    ("let t (x : int * bool) = x", "val t : int * bool -> int * bool"),
    (
        "let h (x : (int -> int) list) = x",
        "val h : (int -> int) list -> (int -> int) list",
    ),
]


@pytest.mark.parametrize(("source", "expected"), SCHEMES)
def test_a_scheme_is_what_ocaml_would_print(
    ocaml: Modules, source: str, expected: str
) -> None:
    from ocaml.middle.infer import signature

    assert signature(ocaml["parse"](source)) == [expected]


def test_an_annotation_after_parameters_is_the_result_type(ocaml: Modules) -> None:
    """`let f x : t = e` gives `e` the type `t`, not `f`.

    Reading it the other way typed `let translate (dx : float) : transform`
    as `float -> transform` and the corpus refused to type.
    """
    from ocaml.middle.infer import signature

    source = "type t = int -> int  let make (n : int) : t = fun x -> x + n"
    # `ocamlc -i` keeps the abbreviation, so the result prints as `t`.
    assert signature(ocaml["parse"](source)) == ["val make : int -> t"]


def test_a_format_is_typed_from_its_directives(ocaml: Modules) -> None:
    """`printf "%3d: %s\\n"` takes an `int` and then a `string`, as in OCaml."""
    from ocaml.middle.infer import signature
    from ocaml.middle.unify import TypingError

    source = (
        'let line n name = Printf.printf "%3d: %s\\n" n name '
        'let label x = Printf.sprintf "<%.2f>" x'
    )
    assert signature(ocaml["parse"](source)) == [
        "val line : int -> string -> unit",
        "val label : float -> string",
    ]
    with pytest.raises(TypingError, match="%a"):
        signature(ocaml["parse"]('let f x = Printf.printf "%a" x'))


def test_a_format_renders_as_ocaml_renders_it(ocaml: Modules, capsys: Any) -> None:
    """Checked against `ocaml`: widths, precision, `%B`, `%c`, `%x`, `%%`."""
    from ocaml.back.interpret import run_source

    run_source(
        "let () = Printf.printf \"%5.1f|%-3d|%B|%c|%x|%%\\n\" 3.14159 7 true 'z' 255"
    )
    assert capsys.readouterr().out == "  3.1|7  |true|z|ff|%\n"


def test_a_label_two_records_share_is_resolved_by_type(ocaml: Modules) -> None:
    """The known type decides, then the later declaration. Checked with `ocamlc -i`."""
    from ocaml.middle.infer import signature

    source = (
        "type a = { id : int; x : int }  type b = { id : int; y : bool } "
        "let f (v : a) = v.id  let g v = v.id  let mk = { id = 1; x = 2 }"
    )
    assert signature(ocaml["parse"](source)) == [
        "val f : a -> int",
        "val g : b -> int",
        "val mk : a",
    ]


def test_an_abbreviation_keeps_its_name(ocaml: Modules) -> None:
    """`ocamlc -i` prints `word` where the programme wrote it, and where a
    type first seen as `int list` later meets `word`."""
    from ocaml.middle.infer import signature

    source = (
        "type word = int list "
        "let rec size (w : word) = match w with [] -> 0 | _ :: r -> 1 + size r "
        "let total w = size w + List.length w"
    )
    assert signature(ocaml["parse"](source)) == [
        "val size : word -> int",
        "val total : word -> int",
    ]


def test_read_line_raises_end_of_file(
    ocaml: Modules, capsys: Any, monkeypatch: Any
) -> None:
    """It returned an empty string after the last line, which OCaml does not."""
    import io

    from ocaml.back.interpret import run_source

    monkeypatch.setattr("sys.stdin", io.StringIO("one\n"))
    run_source(
        "let rec loop () = print_endline (read_line ()); loop () "
        'let () = try loop () with End_of_file -> print_string "done"'
    )
    assert capsys.readouterr().out == "one\ndone"


# ---------------------------------------------------------------- the tutorial
#
# `docs/src/caml/` explains this compiler by quoting it and by showing what
# it prints. Both kinds of claim are checked here, so a page cannot drift
# from the code the way a hand-written walkthrough does.


def _blocks(pattern: str) -> list[tuple[Path, str, str]]:
    """(page, the fence's info string, the block) over every documentation set."""
    fence = re.compile(rf"```({pattern}[^\n]*)\n(.*?)```", re.DOTALL)
    found: list[tuple[Path, str, str]] = []
    for root in DOC_ROOTS:
        for page in sorted(root.rglob("*.md")):
            found += [
                (page, info, block)
                for info, block in fence.findall(page.read_text(encoding="utf-8"))
            ]
    return found


def test_the_tutorial_quotes_the_source_exactly(ocaml: Modules) -> None:
    """A block labelled with a filename has to be that file's text.

    ```python title="src/ocaml/front/parser.py"

    Says to a reader where the code came from, and to this test what to
    compare it with. A block with no title is an illustration rather than a
    quotation and is left alone.
    """
    root = EXAMPLE.parents[1]
    for page, info, block in _blocks("python"):
        found = re.search(r'title="([^"]+)"', info)
        if found is None:
            continue
        named = found.group(1)
        path = EXAMPLE / named if (EXAMPLE / named).exists() else root / named
        assert path.is_file(), f"{page.name}: no such file, {named}"
        text = path.read_text(encoding="utf-8")
        assert block.rstrip() in text, f"{page.name}: not in {named}\n{block}"


def test_the_tutorial_transcripts_are_what_it_prints(
    ocaml: Modules, tmp_path: Path
) -> None:
    """Every `$ python -m ocaml ...` block prints what the page says.

    A command marked `# abridged` shows part of the output on purpose and is
    skipped; everything else has to match to the byte.
    """
    from ocaml.pipeline import VIEWS, analyse

    for page, _info, block in _blocks("console"):
        command, _, expected = block.partition("\n")
        # A console block may also be an error message rather than a
        # transcript; only the ones that show a command are run.
        abridged = "abridged" in command or "abrégé" in command
        if not command.startswith("$ python -m ocaml") or abridged:
            continue
        words = command.removeprefix("$ python -m ocaml").split()
        wanted = next(
            (w.removeprefix("--") for w in words if w.startswith("--")), "run"
        )
        assert wanted in VIEWS, command
        named = words[-1]
        # Beside the page first: both editions have a `tour.ml`, and an
        # English page must not be checked against the French one.
        here = next((r for r in DOC_ROOTS if page.is_relative_to(r)), None)
        roots = [here, *DOC_ROOTS] if here else list(DOC_ROOTS)
        beside = next((found for r in roots for found in r.rglob(named)), None)
        target = beside if beside is not None else EXAMPLE / named
        found = analyse(target.read_text(encoding="utf-8"))
        assert found["errors"] == [], f"{page.name}: {found['errors']}"
        text = found[wanted]
        printed = text if text.endswith("\n") else f"{text}\n"
        assert printed == expected, f"{page.name}: {command}"


# ------------------------------------------------------------- the help pages


def test_the_reference_card_is_generated_from_the_compiler(
    ocaml: Modules, tmp_path: Path
) -> None:
    """The reference card's three tables are read off the compiler.

    So the documentation cannot fall behind it: an operator added to
    `LEVELS`, a keyword added to the lexer or a name added to the prelude
    appears on the page. This is what says so.
    """
    import build

    from ocaml.front.lexer import KEYWORDS
    from ocaml.front.parser import LEVELS
    from ocaml.middle.prelude import PRELUDE_TYPES

    for lang in build.LANGUAGES:
        page = build.reference(lang).read_text(encoding="utf-8")
        assert "<!--" not in page, f"{lang}: a marker was left unfilled"
        for word in KEYWORDS:
            assert f"`{word}`" in page, (lang, word)
        # `build.code` is what wrote them, so it is what looks for them: a
        # `|` inside a table cell has to be escaped, and one place knows how.
        for ops, _ in LEVELS:
            for operator in ops:
                assert build.code(operator) in page, (lang, operator)
        for name in PRELUDE_TYPES:
            assert build.code(name) in page, (lang, name)


def test_the_playground_has_a_string_for_everything(
    ocaml: Modules, tmp_path: Path
) -> None:
    """Nothing the reader sees is written in the markup or the code.

    `index.template.html` carries a `{{...}}` for every string and `app.js`
    reads the rest out of `window.STRINGS`, so an untranslated message shows
    up as an unfilled placeholder rather than as English on a French page.
    """
    import build

    for lang in build.LANGUAGES:
        page = build.playground(lang, tmp_path / lang).read_text(encoding="utf-8")
        assert "{{" not in page, lang
        for wanted in ("../language/playground/", "../language/tour/"):
            assert wanted in page, (lang, wanted)

    code = (EXAMPLE / "web/app.js").read_text(encoding="utf-8")
    for name in build.RUNTIME_STRINGS:
        assert f"S.{name}" in code, name


def test_every_page_can_switch_language(ocaml: Modules, tmp_path: Path) -> None:
    """From any page of one edition, the other edition's copy is one click.

    The header's selector points at each edition's root, so `lang.js`
    rewrites it to the matching page; the playground has no Material header
    and carries its own link. Both are checked here because a reader who
    switches and lands on the home page has lost their place.
    """
    import build

    for lang in EDITIONS:
        other = "fr" if lang == "en" else "en"
        config = (DOCS / f"zensical.{lang}.toml").read_text(encoding="utf-8")
        assert 'extra_javascript = ["lang.js"]' in config, lang
        assert f'link = "/{other}/"' in config, lang

        script = (DOCS / lang / "src" / "lang.js").read_text(encoding="utf-8")
        assert "md-select__link" in script, lang
        assert "caml-prepa:lang" in script, lang
        # `zensical serve` serves one edition at its own root, where the
        # other language is not there at all. The selector is hidden rather
        # than left pointing at that server's 404 page.
        assert "md-header__option" in script, lang
        assert "hidden = true" in script, lang

        page = build.playground(lang, tmp_path / lang).read_text(encoding="utf-8")
        assert f'href="../../{other}/play/"' in page, lang


def test_the_two_editions_have_the_same_pages(ocaml: Modules) -> None:
    """A page added to one edition has an obvious place in the other.

    The same files in the same folders, so a reader switching languages
    lands somewhere, and a translator sees at a glance what is missing.
    """
    shapes = {
        lang: {
            str(path.relative_to(DOCS / lang / "src"))
            for path in (DOCS / lang / "src").rglob("*.md")
            if path.name != "reference.md"
        }
        for lang in EDITIONS
    }
    assert shapes["en"] == shapes["fr"], shapes["en"] ^ shapes["fr"]


def test_the_chooser_offers_both_editions(ocaml: Modules) -> None:
    """The root page sends a reader on, and can be read on purpose."""
    page = (DOCS / "index.html").read_text(encoding="utf-8")
    for lang in EDITIONS:
        assert f'href="{lang}/"' in page, lang
    assert "#stay" in page, "no way to stay on the chooser"
    assert "navigator.languages" in page, "no browser preference"
    assert "localStorage" in page, "a choice is not remembered"


# --------------------------------------------------- the pipeline and the page


def test_the_pipeline_reports_every_stage(ocaml: Modules) -> None:
    """`analyse` is what both front doors call, and this is its contract.

    `python -m ocaml` prints one of its views and the page renders all five,
    so a stage that stopped filling its key would blank a view rather than
    fail.
    """
    from ocaml.pipeline import VIEWS, analyse

    found = analyse(CORPUS[0].read_text(encoding="utf-8"))
    assert found["errors"] == []
    assert found["ran"] is True
    assert found["agree"] is True, "the two back ends printed different things"
    for view in VIEWS:
        assert found[view], view


def test_the_pipeline_reports_a_mistake_rather_than_raising(
    ocaml: Modules,
) -> None:
    """What a compiler produces when you make a mistake is the message."""
    from ocaml.pipeline import analyse

    assert analyse("let x = ")["errors"][0].startswith("syntax:")
    assert "bool" in analyse("let a = 1 + true")["errors"][0]
    assert analyse("let a = nope 1")["errors"] != []


def test_the_playground_bundle_holds_the_whole_toolchain(
    ocaml: Modules, tmp_path: Path
) -> None:
    """The browser fetches one zip, so it has to hold everything.

    Built here rather than checked, so the test says whether the bundler is
    complete rather than whether somebody remembered to run it.
    """
    import zipfile

    import build

    made = zipfile.ZipFile(build.main(tmp_path / "playground.zip"))
    inside = set(made.namelist())
    assert {f"corpus/{path.name}" for path in CORPUS} <= inside
    assert {
        f"ocaml/{path.relative_to(SOURCE)}"
        for path in SOURCE.rglob("*.py")
        if "__pycache__" not in path.parts
    } <= inside
    library = EXAMPLE.parents[1] / "src" / "astero"
    assert {
        f"astero/{path.relative_to(library)}"
        for path in library.rglob("*.py")
        if "__pycache__" not in path.parts
    } <= inside


# --------------------------------------------------------------- the prelude


def test_the_resolver_and_the_runtime_share_one_table(ocaml: Modules) -> None:
    """The initial environment is the runtime's exports, not a copy of them."""
    from ocaml.back import runtime

    prelude = ocaml["analyze"].PRELUDE
    assert prelude[ocaml["grammar"].VALS] == frozenset(runtime.ENV)


def test_every_operator_has_a_value(ocaml: Modules) -> None:
    """`( + )` is a value, so every row of `LEVELS` needs one in `ENV`.

    Three files, one fact: the parser's table, the runtime's implementations
    and the resolver's initial environment. A row added to `LEVELS` without
    an implementation fails here.
    """
    from ocaml.back import runtime
    from ocaml.front.parser import OPERATOR_NAMES

    assert set(OPERATOR_NAMES) <= set(runtime.ENV)
    assert set(OPERATOR_NAMES) - {"!"} <= set(runtime.BINARY_OPS)


# ----------------------------------------------------------------- compiling


def _run_compiled(source: str, path: str = "<corpus>") -> dict[str, Any]:
    from ocaml.back.compile import compile_source

    scope: dict[str, Any] = {"__name__": "__main__"}
    exec(compile(compile_source(source), path, "exec"), scope)
    return scope


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_compiler_agrees_with_the_interpreter(
    ocaml: Modules, path: Path, capsys: Any
) -> None:
    """The differential test phase 5 exists for.

    Two back ends over one runtime, so a disagreement is a defect in one of
    them rather than a difference between two languages. It found one: the
    interpreter let a top-level `let` write into the scope a closure had
    already captured.
    """
    from ocaml.back.interpret import run_source

    source = path.read_text(encoding="utf-8")
    expected = path.with_suffix(".expected").read_text(encoding="utf-8")

    _run_compiled(source, str(path))
    compiled = capsys.readouterr().out
    run_source(source)
    walked = capsys.readouterr().out

    assert compiled == walked
    assert compiled == expected


def test_a_closure_keeps_the_binding_it_captured(ocaml: Modules) -> None:
    """`let x = 2` after a closure is a new binding, not an assignment.

    OCaml answers 1. The interpreter answered 2 until the compiled
    programme disagreed with it.
    """
    from ocaml.back.interpret import run_source

    source = "let x = 1  let f = fun () -> x  let x = 2  let y = f ()"
    assert run_source(source)["y"] == 1
    assert _run_compiled(source)["y"] == 1


def test_the_emitted_source_is_python(ocaml: Modules) -> None:
    import ast as python_ast

    from ocaml.back.compile import compile_source

    for path in CORPUS:
        python_ast.parse(compile_source(path.read_text(encoding="utf-8")))


#: What the emitted text must contain, and why it is worth reading.
EMITTED = [
    # Arity: two parameters becomes a two-parameter `def`, and a saturated
    # call becomes a direct call rather than `runtime.apply`.
    ("let add a b = a + b  let n = add 1 2", ["def add(a, b):", "n = add(1, 2)"]),
    # A partial application cannot be a direct call, so it goes through
    # `apply`, which is where arity is worked out at run time.
    ("let add a b = a + b  let inc = add 1", ["_rt.apply(add, 1)"]),
    # `'` is legal in an OCaml identifier and not in a Python one.
    ("let x' = 1  let y = x' + 1", ["x_ = 1"]),
    # A shadowing binding takes a fresh name, so an earlier closure keeps
    # reading the one it captured.
    ("let x = 1  let f = fun () -> x  let x = 2", ["x = 1", "x_2 = 2"]),
    # Only the prelude names actually used are bound in the preamble.
    ("let () = print_int 1", ["print_int = _rt.ENV['print_int']"]),
    # `+` is Python's `+`; `/` and `<=` are not, so they read the table.
    ("let f a b = a + b", ["a + b"]),
    ("let f a b = a / b", ["_rt.BINARY_OPS['/']"]),
    ("let f a b = a <= b", ["_rt.BINARY_OPS['<=']"]),
    ("let f a b = a = b", ["_rt.equal(a, b)"]),
]


@pytest.mark.parametrize(("source", "wanted"), EMITTED)
def test_the_emitted_python_says_what_it_should(
    ocaml: Modules, source: str, wanted: list[str]
) -> None:
    from ocaml.back.compile import compile_source

    found = compile_source(source)
    for fragment in wanted:
        assert fragment in found, found


def test_every_prelude_value_takes_one_argument(ocaml: Modules) -> None:
    """The compiler emits `f(a)(b)` for a prelude call and relies on this.

    A curried `ENV` entry is what makes that exact. An entry added as a
    plain two-argument Python function would break it silently, so the
    invariant is asserted rather than assumed.
    """
    from ocaml.back import runtime

    wrong = {key for key, value in runtime.ENV.items() if runtime.arity(value) != 1}
    assert wrong == set()


def test_the_compiler_handles_every_production(ocaml: Modules) -> None:
    from astero.coverage import Coverage, match_arms
    from ocaml.back import compile as backend

    found = Coverage(
        handled=match_arms(
            backend.Lowering.expr,
            backend.lower_item,
            backend.tests,
            backend.bindings,
            backend.expand,
        ),
        expected=ocaml["grammar"].OCAML.concrete(),
        accounted={
            "reached through the production that owns it": frozenset({
                "Binding",
                "Case",
                "FieldBind",
                "PField",
                "Structure",
            }),
            "a declaration, which emits nothing": frozenset({
                "AliasDef",
                "FieldDef",
                "RecordDef",
                "TCon",
                "TFun",
                "TTuple",
                "TVar",
                "TypeDef",
                "Variant",
                "Variants",
            }),
        },
    )
    assert not found.missing, found.explain()
    assert not found.absent, found.explain()
    assert not found.redundant, found.explain()


# ------------------------------------------------------------------ stepping


@pytest.fixture(scope="module")
def walked(ocaml: Modules) -> Any:
    """One recorded run, for the tests that read a trace."""
    from ocaml.back import stepper

    return stepper.record(
        "let rec sum l =\n"
        "  match l with\n"
        "  | [] -> 0\n"
        "  | t :: rest -> t + sum rest\n"
        "let () = print_int (sum [3; 1; 4])\n"
    )


def test_a_trace_runs_the_programme_it_records(ocaml: Modules, walked: Any) -> None:
    """Recording changes what a programme costs, never what it does."""
    assert walked.output == "8"
    assert walked.error is None
    assert not walked.truncated
    assert walked.steps


def test_watching_costs_nothing_when_nobody_watches(ocaml: Modules) -> None:
    """The hook is off after a recording, whatever the recording did."""
    from ocaml.back import interpret, stepper

    assert interpret.watching is None
    with contextlib.suppress(Exception):
        stepper.record('let () = failwith "no"')
    assert interpret.watching is None


def test_every_step_points_at_the_source_it_is_evaluating(
    ocaml: Modules, walked: Any
) -> None:
    """The mark in the editor is the span, so a wrong span is a wrong mark."""
    for step in walked.steps:
        assert step.span is not None
        assert step.kind in {"enter", "value"}


def test_a_value_step_knows_what_it_produced(ocaml: Modules, walked: Any) -> None:
    """`sum [3; 1; 4]` is 8, and the step that produced it says so."""
    tops = [
        step
        for step in walked.steps
        if step.kind == "value" and step.stack == ("top", "print_int", "sum")
    ]
    assert tops
    assert tops[-1].value == "8"


def test_stepping_out_lands_in_the_caller(ocaml: Modules, walked: Any) -> None:
    """Step in, over and out count calls, not sub-expressions.

    Every operand of an expression is deeper than the expression and none of
    them is a call, so `depth` is the wrong thing to step by and `call` is
    the right one. This holds the distinction.
    """
    deepest = max(walked.steps, key=lambda step: step.call)
    assert deepest.call > 2
    after = [step for step in walked.steps if step.call < deepest.call]
    assert after, "a call the trace never leaves"


def test_a_value_is_shown_the_way_ocaml_shows_it(ocaml: Modules) -> None:
    """The step view renders values, and a debugger `repr` would not do."""
    from ocaml.back import runtime, stepper

    assert stepper.show(runtime.from_python([3, 1, 4])) == "[3; 1; 4]"
    assert stepper.show([1, 2]) == "[|1; 2|]"
    assert stepper.show(runtime.Record({"contents": 0})) == "{ contents = 0 }"
    assert stepper.show(runtime.Value("Some", (1,))) == "Some 1"
    assert stepper.show(runtime.Value("[]")) == "[]"
    assert stepper.show(True) == "true"
    assert stepper.show(None) == "()"
    assert stepper.show(2.0) == "2."


def test_two_names_for_one_cell_are_one_row(ocaml: Modules) -> None:
    """The store is separate from the environment so aliasing is visible."""
    from ocaml.back import stepper

    trace = stepper.record("let r = ref 0\nlet s = r\nlet () = r := 7; print_int !s\n")
    assert trace.output == "7"
    shown = [dict(step.store) for step in trace.steps if step.store]
    assert shown, "nothing mutable was ever recorded"
    # One cell, both names on it, and the assignment through `r` is what `s`
    # now reads. Two rows here would mean the store was copying.
    assert all(len(cells) == 1 for cells in shown)
    assert {"s, r", "r, s"} & set(shown[-1])
    assert "{ contents = 7 }" in shown[-1].values()


def test_the_scope_of_a_step_comes_from_the_declaration(
    ocaml: Modules, walked: Any
) -> None:
    """The stepper and the Names view read one declaration, so they agree.

    `SCOPES` says a `match` arm opens a scope over its pattern and body, and
    that is the only place either of them learns it.
    """
    inside = {step.scope for step in walked.steps if step.env}
    assert any(scope.endswith("case") for scope in inside)
    assert all(scope.startswith("top") for scope in inside)


def test_a_runaway_programme_still_returns(ocaml: Modules) -> None:
    """The limit is what keeps a loop from filling the browser's memory."""
    from ocaml.back import stepper

    trace = stepper.record(
        "let () =\n  for i = 1 to 10000 do print_char '.' done\n", limit=200
    )
    assert trace.truncated
    assert len(trace.steps) <= 220
    # Recording stopped; the programme did not.
    assert len(trace.output) == 10000


def test_both_back_ends_print_the_same_thing_while_stepping(ocaml: Modules) -> None:
    """The Step view lines the two up on output, so they have to agree on it."""
    from ocaml.back import stepper

    for path in (EXAMPLE / "corpus/fact.ml", EXAMPLE / "corpus/lists.ml"):
        source = path.read_text(encoding="utf-8")
        walked_out = stepper.record(source).output
        steps, compiled_out = stepper.record_compiled(source)
        assert walked_out == compiled_out, path.name
        assert steps, path.name
        assert all(step.printed <= len(compiled_out) for step in steps)


def test_the_step_view_has_a_string_for_everything(ocaml: Modules) -> None:
    """Both editions, or the panel comes out with a `{{placeholder}}` in it."""
    import build

    for lang in build.LANGUAGES:
        words = build.PLAYGROUND[lang]
        assert words["tab_step"]
        for name in ("start", "out", "back", "forward", "in", "end", "at", "cursor"):
            assert words[f"step_{name}"], (lang, name)
    assert {"recording", "steps", "evaluating", "gives"} <= set(build.RUNTIME_STRINGS)


# ------------------------------------------------------------------- hygiene


def test_renaming_reaches_binders_and_uses_and_nothing_else(ocaml: Modules) -> None:
    """`rename` over a grammar with no Python in it.

    The namespace is what keeps it off `r.x`: a record label is an
    identifier slot too, in `fields`, and a rename over `vals` must not
    rewrite one.
    """
    from astero.python.hygiene import rename

    g = ocaml["grammar"]
    tree = ocaml["parse"]("let f x = x + r.x")
    renamed = rename(tree, {"x": "z"}, g.OCAML, g.VALS)
    binding = renamed.items[0].bindings[0]
    assert binding.params[0].name == "z"
    assert binding.value.left.name == "z"
    assert binding.value.right.label == "x"
