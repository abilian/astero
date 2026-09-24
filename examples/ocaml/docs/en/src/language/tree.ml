type 'a tree =
  | Leaf
  | Node of 'a tree * 'a * 'a tree

let rec height t =
  match t with
  | Leaf -> 0
  | Node (l, _, r) -> 1 + max (height l) (height r)
