(* Mutual recursion with `and`, at the top level and inside a `let`. *)

let rec even n = if n = 0 then true else odd (n - 1)
and odd n = if n = 0 then false else even (n - 1)

type expr =
  | Num of int
  | Add of expr * expr
  | Mul of expr * expr
  | Neg of expr

let rec eval e =
  match e with
  | Num n -> n
  | Add (a, b) -> eval a + eval b
  | Mul (a, b) -> eval a * eval b
  | Neg a -> -eval a

let rec depth e =
  match e with
  | Num _ -> 1
  | Neg a -> 1 + depth a
  | Add (a, b) | Mul (a, b) -> 1 + max (depth a) (depth b)

let flatten e =
  let rec walk e acc =
    match e with
    | Num n -> n :: acc
    | Neg a -> walk a acc
    | Add (a, b) | Mul (a, b) -> walk a (walk b acc)
  in
  walk e []

let () =
  let e = Add (Num 1, Mul (Num 2, Neg (Num 3))) in
  print_int (eval e);
  print_char ' ';
  print_int (depth e);
  print_char ' ';
  print_int (List.length (flatten e));
  print_newline ();
  print_string (if even 4 then "even" else "odd")
