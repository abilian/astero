"""Declared grammars, and the structural facts derived from them.

**"Grammar" here is not a parser's grammar.** astero does not parse. Three
different things carry the name, and only the third is this one:

- Python's PEG grammar (`Grammar/python.gram`) turns text into a tree.
- CPython's ASDL (`Parser/Python.asdl`) declares the shape of the nodes that
  tree is made of. The `ast` module is generated from it, and from 3.13
  `ast._field_types` exposes it at run time.
- A grammar in this library is that node declaration **plus a role per field**,
  which is the part neither of the other two records.

The distinction matters because the roles are the only authored part. A grammar
is sorts, productions, and fields; each field carries a shape, a sort, and a
**role**. Shapes and sorts are read from whatever already declares them — the
interpreter for Python, the annotations for a dataclass IR. The roles are what
ASDL does not have, and they are what the derivations below need:

    child      structural containment, drives traversal
    attr       plain data, never traversed
    def(ns)    introduces a name in namespace `ns`
    use(ns)    refers to a name in namespace `ns`
    defuse(ns) both, for read-modify-write positions
    del(ns)    removes a name

A role belongs to the *parent's field*, not to the child node. That is what
makes `ctx` derivable: `ctx` describes the position a `Name` occupies, so the
position owns it.

Nothing here parses or rewrites. It answers questions about a declared grammar,
and every answer replaces a table that is written by hand somewhere.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

# ----------------------------------------------------------------- conditions
#
# A rule sometimes depends on a sibling field: `import a.b` binds `a` while
# `import a.b as c` binds `c` alone, and a PEP 695 type-parameter scope exists
# only when `type_params` is non-empty. Both ask the same closed question, so
# the condition language is two words rather than a predicate. Admitting an
# arbitrary callable here would readmit host code into the declaration, which
# is the thing this design exists to remove.


@dataclass(frozen=True)
class Present:
    """The field exists and is neither None nor empty."""

    field: str

    def holds(self, node: Any) -> bool:
        return bool(getattr(node, self.field, None))

    def __str__(self) -> str:
        return f"present({self.field})"


@dataclass(frozen=True)
class Absent:
    """The field is missing, None, or empty."""

    field: str

    def holds(self, node: Any) -> bool:
        return not bool(getattr(node, self.field, None))

    def __str__(self) -> str:
        return f"absent({self.field})"


Condition = Present | Absent


# --------------------------------------------------------------------- roles


class Kind(enum.Enum):
    CHILD = "child"
    ATTR = "attr"
    DEF = "def"
    USE = "use"
    DEFUSE = "defuse"
    DEL = "del"
    #: Names a binding that lives in an enclosing or global scope, so the
    #: current scope does not own it. Python's `global` and `nonlocal`.
    DECLARE = "declare"


@dataclass(frozen=True)
class Role:
    kind: Kind
    ns: str | None = None

    def __str__(self) -> str:
        return self.kind.value if self.ns is None else f"{self.kind.value}({self.ns})"

    @property
    def binds(self) -> bool:
        return self.kind in {Kind.DEF, Kind.DEFUSE}

    @property
    def reads(self) -> bool:
        return self.kind in {Kind.USE, Kind.DEFUSE}


CHILD = Role(Kind.CHILD)
ATTR = Role(Kind.ATTR)


def defines(ns: str) -> Role:
    return Role(Kind.DEF, ns)


def uses(ns: str) -> Role:
    return Role(Kind.USE, ns)


def defuse(ns: str) -> Role:
    return Role(Kind.DEFUSE, ns)


def deletes(ns: str) -> Role:
    return Role(Kind.DEL, ns)


def declares(ns: str) -> Role:
    return Role(Kind.DECLARE, ns)


# ---------------------------------------------------------------- structure


class Shape(enum.Enum):
    ONE = "one"
    OPT = "opt"
    SEQ = "seq"
    #: The grammar's source did not report it. `ast._field_types` supplies
    #: shapes from Python 3.13 on; earlier interpreters expose only names.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Field:
    name: str
    role: Role = CHILD
    shape: Shape = Shape.ONE
    #: When set, the role applies only where the condition holds. Static
    #: queries report the field regardless; a consumer holding a node asks.
    #: The sort this field holds, or None when the grammar's source does not
    #: report it. `ast._field_types` supplies it from Python 3.13 on; earlier
    #: interpreters expose only field names.
    sort: str | None = None
    when: Condition | None = None

    def applies(self, node: Any) -> bool:
        """Whether this field's role is in force for `node`."""
        return self.when is None or self.when.holds(node)


@dataclass(frozen=True)
class Production:
    name: str
    fields: tuple[Field, ...] = ()
    sort: str | None = None
    traits: frozenset[str] = frozenset()
    #: The class a rewrite instantiates for this production. Set when the
    #: grammar describes a host that has node classes; a grammar that only
    #: answers questions about a language does not need it.
    cls: type | None = None

    def field(self, name: str) -> Field | None:
        """The field called `name`, or None if this production has none.

        For a caller *asking* whether a field exists. A caller that knows it
        does wants `production[name]`, which raises instead of handing back
        a `Field | None` every use has to re-check.
        """
        return next((f for f in self.fields if f.name == name), None)

    def __getitem__(self, name: str) -> Field:
        """The field called `name`. Raises `KeyError` if there is none.

        The twin of `Grammar[production]`, and the same reason: a lookup
        whose absence is a mistake should say so where the mistake is.
        """
        found = self.field(name)
        if found is None:
            msg = f"{self.name} has no field {name!r}"
            raise KeyError(msg)
        return found

    def __contains__(self, name: object) -> bool:
        return any(f.name == name for f in self.fields)


@dataclass(frozen=True)
class Grammar:
    """A declared language: productions, and the namespaces its names live in."""

    name: str
    productions: Mapping[str, Production]
    namespaces: frozenset[str] = frozenset()
    #: Terminal sorts that hold identifiers, so `ident_slots` can find them.
    ident_sorts: frozenset[str] = frozenset({"ident"})
    #: Sorts whose value is a **reference object** rather than a bare string:
    #: the identifier lives in the named field of that object. postpile's SSA
    #: names an operand with a `Value(name, dtype)`, so its grammar declares
    #: `{"Value": "name"}` and `reference_slots` then finds the operands that
    #: `ident_slots` cannot, because the name is one level down.
    reference_sorts: Mapping[str, str] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Production]:
        return iter(self.productions.values())

    def __getitem__(self, name: str) -> Production:
        return self.productions[name]

    def __contains__(self, name: object) -> bool:
        return name in self.productions

    # ------------------------------------------------------------ queries

    def positions(
        self, kind: Kind | Iterable[Kind], ns: str | None = None
    ) -> dict[str, tuple[str, ...]]:
        """Production name -> field names holding `kind` in namespace `ns`.

        This is the query that replaces a hand-written operand table. It spans
        every production, so a sort the author forgot cannot be missed.
        """
        kinds = {kind} if isinstance(kind, Kind) else set(kind)
        out = {}
        for prod in self:
            names = tuple(
                dict.fromkeys(
                    f.name
                    for f in prod.fields
                    if f.role.kind in kinds and (ns is None or f.role.ns == ns)
                )
            )
            if names:
                out[prod.name] = names
        return out

    def operands(self, ns: str) -> dict[str, tuple[str, ...]]:
        """Fields that read a name from `ns`. The def-use graph's edges."""
        return self.positions((Kind.USE, Kind.DEFUSE), ns)

    def definitions(self, ns: str) -> dict[str, tuple[str, ...]]:
        """Fields that introduce a name in `ns`."""
        return self.positions((Kind.DEF, Kind.DEFUSE), ns)

    # The two above answer "which fields", spanning every node of a production.
    # A pass holding one node wants "which values", and the difference is the
    # conditions: postpile's `AssignValue.target` is a definition or a use
    # depending on `declare`, so a static table has to report both and only an
    # instance can say which. Writing that walk per consumer is what these
    # replace.

    def reads(self, node: Any, ns: str) -> tuple[Any, ...]:
        """The contents of every slot of `node` that reads a name in `ns`."""
        return self._slots(node, ns, lambda role: role.reads)

    def binds(self, node: Any, ns: str) -> tuple[Any, ...]:
        """The contents of every slot of `node` that introduces a name in `ns`."""
        return self._slots(node, ns, lambda role: role.binds)

    def _slots(
        self, node: Any, ns: str, wanted: Callable[[Role], bool]
    ) -> tuple[Any, ...]:
        name = type(node).__name__
        if name not in self.productions:
            raise KeyError(f"{self.name} declares no production {name!r}")
        out: list[Any] = []
        for f in self[name].fields:
            if f.role.ns != ns or not wanted(f.role) or not f.applies(node):
                continue
            value = getattr(node, f.name, None)
            if value is None:
                continue  # an OPT slot that is empty holds no name
            out.extend(value) if f.shape is Shape.SEQ else out.append(value)
        return tuple(out)

    def reference_slots(
        self, ns: str | None = None
    ) -> dict[str, tuple[tuple[str, str], ...]]:
        """Fields holding a reference object, optionally only in one namespace.

        The sibling of `ident_slots`. A language spells a use one of three
        ways: a node in expression position (Python's `Name`), a bare
        identifier in a field (PL/0's `Assign.name`), or an object carrying
        the name (postpile's `Value`). The first two are identifier slots; the
        third is here, and needs `reference_sorts` declared to be visible at
        all — without it a rename over such a grammar is a silent no-op.

        A **pair** per slot where `ident_slots` gives a name, because a
        reference slot is two facts: the field, and where in the object the
        identifier sits. `reference_sorts` already states the second, and a
        caller that has to look it up again re-derives the filter this method
        just applied — which is how both readers of it grew the same five
        lines re-checking a state that cannot occur here.
        """
        out: dict[str, tuple[tuple[str, str], ...]] = {}
        if not self.reference_sorts:
            return out
        for prod in self:
            slots = []
            for f in prod.fields:
                if f.sort is None or f.sort not in self.reference_sorts:
                    continue
                if f.role.kind is Kind.ATTR:
                    continue
                if ns is not None and f.role.ns != ns:
                    continue
                slots.append((f.name, self.reference_sorts[f.sort]))
            if slots:
                out[prod.name] = tuple(slots)
        return out

    def ident_slots(self, ns: str | None = None) -> dict[str, tuple[str, ...]]:
        """Fields holding a bare identifier, optionally only in one namespace.

        Renaming has to reach every one of these. Enumerating them by hand is
        what dropped `vararg`, `kwarg`, lambda parameters and `async def`
        parameters in the pass this replaces.

        Pass `ns` when renaming means renaming *something in particular*.
        Without it the answer spans namespaces, so it includes `Attribute.attr`
        and `keyword.arg`, and renaming a variable `foo` would rewrite `x.foo`
        into a different attribute.
        """
        out = {}
        for prod in self:
            names = tuple(
                f.name
                for f in prod.fields
                if f.sort in self.ident_sorts
                and f.role.kind is not Kind.ATTR
                and (ns is None or f.role.ns == ns)
            )
            if names:
                out[prod.name] = names
        return out

    def subset(self, names: Iterable[str], *, name: str | None = None) -> Grammar:
        """This grammar restricted to `names`, for declaring a sublanguage.

        A compiler for a Python subset declares its language by naming the
        productions it admits, and everything else — the roles, sorts, shapes
        and conditions — comes from the grammar it is a subset of. Nothing is
        authored twice.

        Productions the subset does not name are simply absent, so a rewrite
        that tries to build one fails at the rule rather than downstream, and
        `concrete()` reports the smaller language.
        """
        keep = frozenset(names)
        unknown = keep - set(self.productions)
        if unknown:
            msg = f"{self.name} has no production {sorted(unknown)}"
            raise KeyError(msg)
        # The abstract bases come too. They are sorts, not productions a
        # sublanguage admits or refuses, and `concrete(sort)` is answered from
        # the classes: a subset that dropped them could no longer be asked
        # which of its productions are expressions, which is a question about
        # the sublanguage and not about what it was cut from.
        # Bound rather than repeated: `self.productions[n].cls` written twice
        # is two expressions to a type checker, so the `is not None` guard
        # narrowed neither the element nor the `issubclass` argument below.
        kept_classes = [
            cls for n in keep if (cls := self.productions[n].cls) is not None
        ]
        keep |= {
            name
            for name, prod in self.productions.items()
            if (base := prod.cls) is not None
            and not prod.fields
            and any(issubclass(cls, base) for cls in kept_classes)
        }
        return Grammar(
            name=name or f"{self.name}-subset",
            productions={n: p for n, p in self.productions.items() if n in keep},
            namespaces=self.namespaces,
            ident_sorts=self.ident_sorts,
            reference_sorts=self.reference_sorts,
        )

    def children(self, prod_name: str) -> tuple[Field, ...]:
        """Fields a structural traversal descends into."""
        return tuple(f for f in self[prod_name].fields if f.role.kind is not Kind.ATTR)

    def with_trait(self, trait: str) -> frozenset[str]:
        """Productions carrying `trait`. Replaces per-instruction enumerations."""
        return frozenset(p.name for p in self if trait in p.traits)

    def constructor(self, name: str) -> type:
        """The class that builds production `name`.

        Matching can work off CPython's classes for any host whose nodes
        subclass them, since every dispatch is an `isinstance`. Construction
        cannot: prescrypt-ng's `Assign` carries a mixin its later passes read,
        so a rewrite has to build that class rather than `ast.Assign`.

        A production the host does not have is an error here rather than a
        fallback, because falling back would build a node the host cannot
        compile and defer the failure to somewhere less obvious.
        """
        # Two `if`s rather than a `match`: the second test is on an
        # *attribute*, and a `case ... if prod.cls is None` guard narrows the
        # subject rather than the attribute, so the return stayed `| None` for
        # every checker.
        prod = self.productions.get(name)
        if prod is None:
            raise KeyError(f"grammar {self.name!r} has no production {name!r}")
        cls = prod.cls
        if cls is None:
            raise KeyError(f"grammar {self.name!r} declares no class for {name!r}")
        return cls

    def concrete(self, base: str | None = None) -> frozenset[str]:
        """Productions that can appear in a tree, optionally only under `base`.

        A grammar read off a class hierarchy contains abstract entries: `stmt`
        and `expr` are productions with no instances. A consumer's dispatch
        table is not obliged to cover those, and is obliged to cover the rest,
        so this is the set a coverage check should compare against.

        Answered from the classes, so it needs a grammar that carries them.
        prescrypt-ng compiles `async def` and has no handler for `await`,
        `async for` or `async with`, which is the shape this finds.
        """
        classes = {p.name: p.cls for p in self if p.cls is not None}
        if not classes:
            raise ValueError(
                f"grammar {self.name!r} declares no classes, so which "
                "productions are abstract cannot be derived"
            )
        abstract = {
            name
            for name, cls in classes.items()
            if any(
                other is not cls and issubclass(other, cls)
                for other in classes.values()
            )
        }
        names = set(classes) - abstract
        if base is not None:
            root = classes.get(base)
            if root is None:
                raise KeyError(f"grammar {self.name!r} has no production {base!r}")
            names = {n for n in names if issubclass(classes[n], root)}
        return frozenset(names)

    def check(self) -> list[str]:
        """Internal consistency. Returns complaints, empty when well-formed."""
        problems = []
        for prod in self:
            seen: set[str] = set()
            conditional: set[str] = set()
            for f in prod.fields:
                # A field may appear twice when each occurrence carries a
                # condition, because one slot can hold two roles: postpile's
                # `AssignValue.target` defines when `declare` is set and uses
                # it otherwise. Repeating it unconditionally is still an error.
                if f.name in seen and not (f.when and f.name in conditional):
                    problems.append(f"{prod.name}.{f.name}: duplicate field")
                if f.when is not None:
                    conditional.add(f.name)
                seen.add(f.name)
                if f.role.ns is not None and f.role.ns not in self.namespaces:
                    problems.append(
                        f"{prod.name}.{f.name}: unknown namespace {f.role.ns!r}"
                    )
                if f.role.kind is Kind.ATTR and f.sort in self.ident_sorts:
                    problems.append(
                        f"{prod.name}.{f.name}: an identifier field marked attr "
                        "is invisible to renaming"
                    )
        return problems


# ------------------------------------------------------------------ building


@dataclass
class GrammarBuilder:
    """Assembles a Grammar. The three front doors all end up here."""

    name: str
    namespaces: set[str] = field(default_factory=set)
    ident_sorts: set[str] = field(default_factory=lambda: {"ident"})
    reference_sorts: dict[str, str] = field(default_factory=dict)
    _productions: dict[str, Production] = field(default_factory=dict)

    def production(
        self,
        name: str,
        *fields_: Field,
        sort: str | None = None,
        traits: Iterable[str] = (),
        cls: type | None = None,
    ) -> GrammarBuilder:
        self._productions[name] = Production(
            name=name,
            fields=tuple(fields_),
            sort=sort,
            traits=frozenset(traits),
            cls=cls,
        )
        return self

    def build(self) -> Grammar:
        grammar = Grammar(
            name=self.name,
            productions=dict(self._productions),
            namespaces=frozenset(self.namespaces),
            ident_sorts=frozenset(self.ident_sorts),
            reference_sorts=dict(self.reference_sorts),
        )
        problems = grammar.check()
        if problems:
            joined = "\n  ".join(problems)
            raise ValueError(f"grammar {self.name!r} is not well-formed:\n  {joined}")
        return grammar


def from_dataclasses(
    name: str,
    classes: Iterable[type],
    *,
    roles: Mapping[str, Mapping[str, Any]] | None = None,
    namespaces: Iterable[str] = (),
    ident_sorts: Iterable[str] = ("ident",),
    reference_sorts: Mapping[str, str] | None = None,
    conditions: Mapping[tuple[str, str], Condition] | None = None,
    traits: Mapping[str, Iterable[str]] | None = None,
    data_sorts: Iterable[str] = ("str", "int", "bool", "float", "object"),
) -> Grammar:
    """A grammar read off annotated dataclasses.

    The third front door, beside `astero.python.build` reading a module of `ast`
    classes and `lang_ssa` written out by hand. A compiler whose IR is already
    dataclasses declares it in place: the field names, sorts and shapes come
    from the annotations, and only the roles are authored.

    `roles` maps a production name to its field roles. A field with no role is
    an `attr` when its sort is plain data and a `child` otherwise, which is the
    answer that keeps traversal complete.

    A field's entry may be a sequence of `(role, condition)` pairs when one
    slot holds two roles. postpile's `AssignValue.target` is defined when
    `declare` is set and used when it is not, so it is declared once each way.
    """
    roles = roles or {}
    conditions = conditions or {}
    traits = traits or {}
    data = set(data_sorts)
    builder = GrammarBuilder(
        name=name,
        namespaces=set(namespaces),
        ident_sorts=set(ident_sorts),
        reference_sorts=dict(reference_sorts or {}),
    )
    for cls in classes:
        if not dataclasses.is_dataclass(cls):
            raise TypeError(f"{cls.__name__} is not a dataclass")
        declared = roles.get(cls.__name__, {})
        fields_: list[Field] = []
        for f in dataclasses.fields(cls):
            sort = sort_of(f.type)
            shape = shape_of(f.type)
            spec = declared.get(f.name)
            if spec is None:
                spec = ATTR if sort in data else CHILD
            # A role, or several with the condition that selects each.
            pairs = (
                spec
                if isinstance(spec, (list, tuple))
                else ((spec, conditions.get((cls.__name__, f.name))),)
            )
            for role, when in pairs:
                fields_.append(
                    Field(name=f.name, role=role, shape=shape, sort=sort, when=when)
                )
        builder.production(
            cls.__name__, *fields_, traits=traits.get(cls.__name__, ()), cls=cls
        )
    return builder.build()


def field_of(
    name: str,
    role: Role = CHILD,
    shape: Shape = Shape.ONE,
    sort: str | None = None,
) -> Field:
    """Terser Field constructor, for declarations written by hand."""
    return Field(name=name, role=role, shape=shape, sort=sort)


def sort_of(annotation: Any) -> str:
    """The sort an annotation names, with its container and optionality gone.

    `list[Value]` and `Value | None` are both the sort `Value`. What varies is
    the shape, which `shape_of` reads from the same text.
    """
    text = str(annotation)
    for prefix in ("list[", "ast.", "<class '", "'>"):
        text = text.replace(prefix, "")
    return text.replace("]", "").replace(" | None", "").strip()


def shape_of(annotation: Any) -> Shape:
    """Read a shape off an `ast._field_types`-style annotation."""
    text = str(annotation)
    if text.startswith("list["):
        return Shape.SEQ
    if "None" in text:
        return Shape.OPT
    return Shape.ONE
