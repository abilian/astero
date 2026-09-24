(* Diviser pour régner : Euclide, exponentiation rapide, dichotomie. *)

let rec pgcd a b = if b = 0 then a else pgcd b (a mod b)
let ppcm a b = a / pgcd a b * b

let rec puissance x n =
  if n = 0 then 1
  else
    let m = puissance x (n / 2) in
    if n mod 2 = 0 then m * m else x * m * m

let dichotomie t x =
  let g = ref 0 and d = ref (Array.length t - 1) in
  let trouve = ref (-1) in
  while !trouve < 0 && !g <= !d do
    let m = (!g + !d) / 2 in
    if t.(m) = x then trouve := m
    else if t.(m) < x then g := m + 1
    else d := m - 1
  done;
  !trouve

(* Le nombre d'inversions, compté pendant un tri fusion. *)
let rec compte_fusion a b =
  match (a, b) with
  | [], l -> (0, l)
  | l, [] -> (0, l)
  | x :: xs, y :: ys ->
      if x <= y then
        let n, reste = compte_fusion xs b in
        (n, x :: reste)
      else
        let n, reste = compte_fusion a ys in
        (n + List.length a, y :: reste)

let rec coupe k l =
  if k = 0 then ([], l)
  else
    match l with
    | [] -> ([], [])
    | t :: q ->
        let g, d = coupe (k - 1) q in
        (t :: g, d)

let rec inversions l =
  let n = List.length l in
  if n <= 1 then (0, l)
  else
    let g, d = coupe (n / 2) l in
    let ng, tg = inversions g in
    let nd, td = inversions d in
    let nf, t = compte_fusion tg td in
    (ng + nd + nf, t)

let () =
  print_int (pgcd 84 36);
  print_char ' ';
  print_int (ppcm 4 6);
  print_char ' ';
  print_int (puissance 2 10);
  print_newline ();
  print_int (dichotomie [| 1; 3; 5; 7; 9 |] 7);
  print_int (dichotomie [| 1; 3; 5; 7; 9 |] 4);
  print_newline ();
  let n, _ = inversions [ 3; 1; 4; 1; 5 ] in
  print_int n
