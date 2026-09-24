(* Programmation dynamique : mémoïsation et tableaux. *)

let fibo n =
  let memo = Array.make (n + 1) (-1) in
  let rec f k =
    if k <= 1 then k
    else if memo.(k) >= 0 then memo.(k)
    else begin
      let v = f (k - 1) + f (k - 2) in
      memo.(k) <- v;
      v
    end
  in
  f n

(* La somme maximale d'un sous-tableau, en une passe. *)
let somme_max t =
  let meilleure = ref t.(0) and courante = ref t.(0) in
  for i = 1 to Array.length t - 1 do
    courante := max t.(i) (!courante + t.(i));
    if !courante > !meilleure then meilleure := !courante
  done;
  !meilleure

let plus_longue_commune a b =
  let n = String.length a and m = String.length b in
  let d = Array.make_matrix (n + 1) (m + 1) 0 in
  for i = 1 to n do
    for j = 1 to m do
      if a.[i - 1] = b.[j - 1] then d.(i).(j) <- d.(i - 1).(j - 1) + 1
      else d.(i).(j) <- max d.(i - 1).(j) d.(i).(j - 1)
    done
  done;
  d.(n).(m)

(* Le rendu de monnaie : le nombre minimal de pièces, ou -1. *)
let rendu pieces somme =
  let grand = somme + 1 in
  let d = Array.make (somme + 1) grand in
  d.(0) <- 0;
  List.iter
    (fun p ->
      for s = p to somme do
        if d.(s - p) + 1 < d.(s) then d.(s) <- d.(s - p) + 1
      done)
    pieces;
  if d.(somme) = grand then -1 else d.(somme)

let () =
  print_int (fibo 30);
  print_newline ();
  print_int (somme_max [| -2; 1; -3; 4; -1; 2; 1; -5; 4 |]);
  print_char ' ';
  print_int (plus_longue_commune "abcbdab" "bdcaba");
  print_char ' ';
  print_int (rendu [ 1; 3; 4 ] 6);
  print_char ' ';
  print_int (rendu [ 5 ] 3)
