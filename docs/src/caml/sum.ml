let rec sum l =
  match l with
  | [] -> 0
  | t :: rest -> t + sum rest
