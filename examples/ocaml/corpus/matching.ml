(* Pattern matching: guards, or-patterns, aliases, nested and typed patterns. *)

type shape =
  | Circle of float
  | Rect of float * float
  | Empty

type 'a option_pair = ('a option * 'a option)

let area s =
  match s with
  | Circle r -> 3.14159 *. r *. r
  | Rect (w, h) -> w *. h
  | Empty -> 0.0

let sign n =
  match n with
  | 0 -> "zero"
  | k when k < 0 -> "negative"
  | _ -> "positive"

let first_two l =
  match l with
  | (a :: b :: _) as whole -> (a, b, List.length whole)
  | [ _ ] | [] -> (0, 0, 0)

let vowel c =
  match c with
  | 'a' | 'e' | 'i' | 'o' | 'u' -> true
  | _ -> false

let corners = function
  | [| a; b |] -> a + b
  | [| a; b; c; d |] -> a + b + c + d
  | _ -> 0

let typed (p : int * bool) =
  match p with
  | (n, true) -> n
  | (n, false) -> -n

let both = function
  | (Some a, Some b) -> a + b
  | (Some a, None) | (None, Some a) -> a
  | (None, None) -> 0

let () =
  print_string (sign (-3));
  print_char ' ';
  print_float (area (Rect (2.0, 3.0)))
