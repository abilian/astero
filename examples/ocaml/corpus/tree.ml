(* A polymorphic binary search tree: sum types, matching, records. *)

type 'a tree =
  | Leaf
  | Node of 'a tree * 'a * 'a tree

exception Empty

let rec insert x t =
  match t with
  | Leaf -> Node (Leaf, x, Leaf)
  | Node (l, y, r) ->
      if x < y then Node (insert x l, y, r)
      else if x > y then Node (l, y, insert x r)
      else t

let rec height = function
  | Leaf -> 0
  | Node (l, _, r) -> 1 + max (height l) (height r)

let rec min_elt t =
  match t with
  | Leaf -> raise Empty
  | Node (Leaf, x, _) -> x
  | Node (l, _, _) -> min_elt l

let rec to_list t =
  match t with
  | Leaf -> []
  | Node (l, x, r) -> to_list l @ (x :: to_list r)

type stats = { mutable count : int; mutable total : int }

let summarise l =
  let acc = { count = 0; total = 0 } in
  List.iter (fun x -> acc.count <- acc.count + 1; acc.total <- acc.total + x) l;
  acc

let () =
  let t = List.fold_left (fun acc x -> insert x acc) Leaf [ 5; 3; 8; 1 ] in
  print_int (height t);
  print_newline ();
  let s = summarise (to_list t) in
  print_int s.total
