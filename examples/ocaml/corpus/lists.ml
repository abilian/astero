(* Lists, higher-order functions, guards, or-patterns, aliases. *)

let rec length l =
  match l with
  | [] -> 0
  | _ :: t -> 1 + length t

let rec map f l =
  match l with
  | [] -> []
  | h :: t -> f h :: map f t

let rec filter p = function
  | [] -> []
  | h :: t when p h -> h :: filter p t
  | _ :: t -> filter p t

let classify n =
  match n with
  | 0 | 1 -> "small"
  | k when k < 0 -> "negative"
  | _ -> "large"

let rec merge cmp xs ys =
  match xs, ys with
  | [], l | l, [] -> l
  | (x :: xt as l1), (y :: yt as l2) ->
      if cmp x y <= 0 then x :: merge cmp xt l2 else y :: merge cmp l1 yt

let compose f g = fun x -> f (g x)

let sum = List.fold_left ( + ) 0
