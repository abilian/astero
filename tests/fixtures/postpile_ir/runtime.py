"""postpile's runtime operation families, declared.

A read-only mirror, like `lang_ssa`. astero imports nothing from postpile.

Sixteen tables in `postpile/src/postpile/compiler/frontend/common.py` are keyed
by element type and share only six distinct key sets. The rule "a Bool crosses
as an Int64" is written three ways across them: `_LIST_APPEND` inlines it as a
key, `_SELECT_SEND` deliberately keys on `_CHAN_WIRE`'s output instead, and
`_OBJ_GET` takes a parameter named `wire` and trusts callers to have normalized
already. postpile's own notes state the lesson (`accept-then-wrong.md` §13): a
predicate spelled identically in N places is one predicate with N-1 chances to
miss an exception.

Here the rule appears once per family, and the holes appear as holes.
"""

from __future__ import annotations

from astero.tables import Family

#: A Bool crosses the wire as an Int64. Stated once, applied to every row.
WIRE = {"Bool": "Int64"}

#: The list runtime. The unchecked twins of ADR 0053 exist for the numeric
#: elements only: a Str element stays on the borrow-classified helpers, and
#: that is a hole rather than a missing key.
LIST = Family.parse(
    "list",
    normalize=WIRE,
    matrix="""
                     Int64            Float64          Str
    append           LIST_APPEND_I64  LIST_APPEND_F64  LIST_APPEND_STR
    get              LIST_GET_I64     LIST_GET_F64     LIST_GET_STR
    set              LIST_SET_I64     LIST_SET_F64     LIST_SET_STR
    has              LIST_HAS_I64     LIST_HAS_F64     LIST_HAS_STR
    get_unchecked    LIST_GET_I64_U   LIST_GET_F64_U   .
    set_unchecked    LIST_SET_I64_U   LIST_SET_F64_U   .
    """,
)

#: Channels and select. `select` has no Bool row in postpile because it is
#: keyed on the wire type already; here that falls out of the same
#: normalization the other rows use, so the two stop being different shapes.
CHAN = Family.parse(
    "chan",
    normalize=WIRE,
    matrix="""
                     Int64                 Float64               Str
    send             PYGO_SEND_I64         PYGO_SEND_F64         PYGO_SEND_STR
    recv             PYGO_RECV_I64         PYGO_RECV_F64         PYGO_RECV_STR
    select_send      PYGO_SELECT_SEND_I64  PYGO_SELECT_SEND_F64  PYGO_SELECT_SEND_STR
    select_read      PYGO_SELECT_I64       PYGO_SELECT_F64       PYGO_SELECT_STR
    """,
)

#: Object fields. postpile's `_OBJ_GET` has no Bool key and its accessor takes
#: a parameter literally named `wire`, so callers normalize first. Declaring
#: the normalization here means they no longer have to.
OBJ = Family.parse(
    "obj",
    normalize=WIRE,
    matrix="""
                     Int64            Float64          Str
    get              OBJ_GET_I64      OBJ_GET_F64      OBJ_GET_STR
    set              OBJ_SET_I64      OBJ_SET_F64      OBJ_SET_STR
    """,
)

FAMILIES = {family.name: family for family in (LIST, CHAN, OBJ)}
