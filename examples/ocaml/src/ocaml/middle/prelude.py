"""What a programme may use without defining it.

`print_int`, `List.map`, `+` — every name that is simply *there*, with the
type OCaml gives it. The types are written as OCaml source and read back
with this compiler's own type grammar, so you can check the table against
the manual rather than against constructor calls:

    "List.fold_left": "('a -> 'b -> 'a) -> 'a -> 'b list -> 'a"

This is a middle-end file because which names are in scope is settled
before anything runs. `back/runtime.py` supplies a *value* for each of these
names, and `test_every_prelude_value_has_a_type` holds the two lists equal,
so neither can quietly grow an entry the other lacks.

Pure data, importing nothing. `analyze` reads the names, `infer` reads the
types, and the playground's build step reads both to generate its reference
page, so adding a function here puts it in the documentation too.
"""

from __future__ import annotations

#: Every name with the type OCaml gives it. Written as source and parsed
#: with this compiler's own type grammar, so a reader checks it against
#: the manual rather than against constructor calls.
PRELUDE_TYPES: dict[str, str] = {
    "not": "bool -> bool",
    "ref": "'a -> 'a ref",
    "incr": "int ref -> unit",
    "decr": "int ref -> unit",
    "ignore": "'a -> unit",
    "fst": "'a * 'b -> 'a",
    "snd": "'a * 'b -> 'b",
    "compare": "'a -> 'a -> int",
    "min": "'a -> 'a -> 'a",
    "max": "'a -> 'a -> 'a",
    "abs": "int -> int",
    "succ": "int -> int",
    "pred": "int -> int",
    "raise": "exn -> 'a",
    "failwith": "string -> 'a",
    "invalid_arg": "string -> 'a",
    "print_int": "int -> unit",
    "print_float": "float -> unit",
    "print_char": "char -> unit",
    "print_string": "string -> unit",
    "print_endline": "string -> unit",
    "print_newline": "unit -> unit",
    "read_int": "unit -> int",
    "read_float": "unit -> float",
    "read_line": "unit -> string",
    "string_of_int": "int -> string",
    "int_of_string": "string -> int",
    "string_of_float": "float -> string",
    "float_of_string": "string -> float",
    "string_of_bool": "bool -> string",
    "bool_of_string": "string -> bool",
    "float_of_int": "int -> float",
    "int_of_float": "float -> int",
    "char_of_int": "int -> char",
    "int_of_char": "char -> int",
    "truncate": "float -> int",
    "sqrt": "float -> float",
    "exp": "float -> float",
    "log": "float -> float",
    "sin": "float -> float",
    "cos": "float -> float",
    "tan": "float -> float",
    "atan": "float -> float",
    "floor": "float -> float",
    "ceil": "float -> float",
    "abs_float": "float -> float",
    "infinity": "float",
    "neg_infinity": "float",
    "max_int": "int",
    "min_int": "int",
    # OCaml's `assert` is a keyword, and `assert false` has any type.
    "assert": "bool -> unit",
    "+": "int -> int -> int",
    "-": "int -> int -> int",
    "*": "int -> int -> int",
    "/": "int -> int -> int",
    "mod": "int -> int -> int",
    "land": "int -> int -> int",
    "lor": "int -> int -> int",
    "lxor": "int -> int -> int",
    "lsl": "int -> int -> int",
    "lsr": "int -> int -> int",
    "asr": "int -> int -> int",
    "+.": "float -> float -> float",
    "-.": "float -> float -> float",
    "*.": "float -> float -> float",
    "/.": "float -> float -> float",
    "**": "float -> float -> float",
    "^": "string -> string -> string",
    "@": "'a list -> 'a list -> 'a list",
    "=": "'a -> 'a -> bool",
    "<>": "'a -> 'a -> bool",
    "<": "'a -> 'a -> bool",
    "<=": "'a -> 'a -> bool",
    ">": "'a -> 'a -> bool",
    ">=": "'a -> 'a -> bool",
    "&&": "bool -> bool -> bool",
    "||": "bool -> bool -> bool",
    ":=": "'a ref -> 'a -> unit",
    "!": "'a ref -> 'a",
    "List.length": "'a list -> int",
    "List.hd": "'a list -> 'a",
    "List.tl": "'a list -> 'a list",
    "List.nth": "'a list -> int -> 'a",
    "List.rev": "'a list -> 'a list",
    "List.append": "'a list -> 'a list -> 'a list",
    "List.concat": "'a list list -> 'a list",
    "List.map": "('a -> 'b) -> 'a list -> 'b list",
    "List.rev_map": "('a -> 'b) -> 'a list -> 'b list",
    "List.mapi": "(int -> 'a -> 'b) -> 'a list -> 'b list",
    "List.iter": "('a -> unit) -> 'a list -> unit",
    "List.iteri": "(int -> 'a -> unit) -> 'a list -> unit",
    "List.fold_left": "('a -> 'b -> 'a) -> 'a -> 'b list -> 'a",
    "List.fold_right": "('a -> 'b -> 'b) -> 'a list -> 'b -> 'b",
    "List.filter": "('a -> bool) -> 'a list -> 'a list",
    "List.exists": "('a -> bool) -> 'a list -> bool",
    "List.find": "('a -> bool) -> 'a list -> 'a",
    "List.filter_map": "('a -> 'b option) -> 'a list -> 'b list",
    "List.for_all": "('a -> bool) -> 'a list -> bool",
    "List.mem": "'a -> 'a list -> bool",
    "List.assoc": "'a -> ('a * 'b) list -> 'b",
    "List.split": "('a * 'b) list -> 'a list * 'b list",
    "List.combine": "'a list -> 'b list -> ('a * 'b) list",
    "List.sort": "('a -> 'a -> int) -> 'a list -> 'a list",
    "List.init": "int -> (int -> 'a) -> 'a list",
    "Array.length": "'a array -> int",
    "Array.make": "int -> 'a -> 'a array",
    "Array.init": "int -> (int -> 'a) -> 'a array",
    "Array.make_matrix": "int -> int -> 'a -> 'a array array",
    "Array.get": "'a array -> int -> 'a",
    "Array.set": "'a array -> int -> 'a -> unit",
    "Array.copy": "'a array -> 'a array",
    "Array.sub": "'a array -> int -> int -> 'a array",
    "Array.append": "'a array -> 'a array -> 'a array",
    "Array.of_list": "'a list -> 'a array",
    "Array.to_list": "'a array -> 'a list",
    "Array.iter": "('a -> unit) -> 'a array -> unit",
    "Array.iteri": "(int -> 'a -> unit) -> 'a array -> unit",
    "Array.map": "('a -> 'b) -> 'a array -> 'b array",
    "Array.fold_left": "('a -> 'b -> 'a) -> 'a -> 'b array -> 'a",
    "Array.sort": "('a -> 'a -> int) -> 'a array -> unit",
    "Array.blit": "'a array -> int -> 'a array -> int -> int -> unit",
    "Array.fill": "'a array -> int -> int -> 'a -> unit",
    "String.length": "string -> int",
    "String.get": "string -> int -> char",
    "String.sub": "string -> int -> int -> string",
    "String.concat": "string -> string list -> string",
    "String.make": "int -> char -> string",
    "String.init": "int -> (int -> char) -> string",
    "String.index": "string -> char -> int",
    "String.contains": "string -> char -> bool",
    "String.uppercase_ascii": "string -> string",
    "String.lowercase_ascii": "string -> string",
    "String.split_on_char": "char -> string -> string list",
    "String.compare": "string -> string -> int",
    "Char.code": "char -> int",
    "Char.chr": "int -> char",
    "Char.escaped": "char -> string",
    "Char.lowercase_ascii": "char -> char",
    "Char.uppercase_ascii": "char -> char",
    # A literal format's type comes from its directives, `infer._format`.
    "Printf.printf": "('a, out_channel, unit) format -> 'a",
    "Printf.sprintf": "('a, unit, string) format -> 'a",
    "Float.pi": "float",
    "Float.exp": "float -> float",
    "Float.cos": "float -> float",
    "Float.sin": "float -> float",
    "Float.tan": "float -> float",
    "Sys.argv": "string array",
    "Random.int": "int -> int",
    "Random.self_init": "unit -> unit",
    "Random.init": "int -> unit",
    "Stack.create": "unit -> 'a Stack.t",
    "Stack.push": "'a -> 'a Stack.t -> unit",
    "Stack.pop": "'a Stack.t -> 'a",
    "Stack.top": "'a Stack.t -> 'a",
    "Stack.is_empty": "'a Stack.t -> bool",
    "Stack.length": "'a Stack.t -> int",
    "Hashtbl.create": "int -> ('a, 'b) Hashtbl.t",
    "Hashtbl.add": "('a, 'b) Hashtbl.t -> 'a -> 'b -> unit",
    "Hashtbl.replace": "('a, 'b) Hashtbl.t -> 'a -> 'b -> unit",
    "Hashtbl.remove": "('a, 'b) Hashtbl.t -> 'a -> unit",
    "Hashtbl.find": "('a, 'b) Hashtbl.t -> 'a -> 'b",
    "Hashtbl.find_opt": "('a, 'b) Hashtbl.t -> 'a -> 'b option",
    "Hashtbl.mem": "('a, 'b) Hashtbl.t -> 'a -> bool",
    "Hashtbl.length": "('a, 'b) Hashtbl.t -> int",
}

#: Prefix `-` and `-.` are not the `-` of `PRELUDE_TYPES`, which is binary
#: subtraction. `!` is the same in both positions and is not repeated.
UNARY_TYPES = {"-": "int -> int", "-.": "float -> float", "!": "'a ref -> 'a"}

#: Constructors no declaration introduces, with the type of each argument.
#: `::` takes two because `Construct` stores components, not a tuple. The
#: arity is `len`, which is why there is no second table of arities.
CONSTRUCTORS: dict[str, tuple[str, ...]] = {
    "[]": (),
    "::": ("'a", "'a list"),
    "None": (),
    "Some": ("'a",),
    "Not_found": (),
    "Exit": (),
    "Division_by_zero": (),
    "Match_failure": (),
    "End_of_file": (),
    "Assert_failure": ("string * int * int",),
    "Failure": ("string",),
    "Invalid_argument": ("string",),
}

CONSTRUCTOR_RESULTS = {
    "[]": "'a list",
    "::": "'a list",
    "None": "'a option",
    "Some": "'a option",
}


#: The type constructors the prelude supplies, with how many arguments each
#: takes. `TYPE_NAMES` is its keys, so the two cannot disagree.
TYPE_ARITY: dict[str, int] = {
    "int": 0,
    "float": 0,
    "char": 0,
    "string": 0,
    "bool": 0,
    "unit": 0,
    "exn": 0,
    "list": 1,
    "array": 1,
    "ref": 1,
    "option": 1,
    # `format` is `('a, 'channel, 'result) format`, and only a string
    # literal written as `printf`'s argument ever has it.
    "format": 3,
    "out_channel": 0,
    "Stack.t": 1,
    "Hashtbl.t": 2,
}

TYPE_NAMES = tuple(TYPE_ARITY)

#: `'a ref = { mutable contents : 'a }`, and that is the whole reason.
FIELD_NAMES = ("contents",)
