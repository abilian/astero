(* Plus longue sous-suite commune.  D'après le TP 3 de Vincent Simonet
   (MPSI, 2001) et le TP 5 (MP, 2003) : la méthode naïve, puis la même
   chose par programmation dynamique, puis la reconstruction d'une
   sous-suite témoin.

   Une sous-suite s'obtient en effaçant des éléments sans changer l'ordre
   des autres : [1; 3] est une sous-suite de [1; 2; 3] mais pas [3; 1]. *)

let rec prefixe n l =
  match (n, l) with
  | 0, _ -> []
  | _, [] -> []
  | _, t :: q -> t :: prefixe (n - 1) q

let rec est_sous_suite petite grande =
  match (petite, grande) with
  | [], _ -> true
  | _ :: _, [] -> false
  | a :: p, b :: q ->
      if a = b then est_sous_suite p q else est_sous_suite petite q

(* Méthode naïve : on essaie les deux façons de raccourcir. *)
let rec longueur_naive x y =
  match (x, y) with
  | [], _ -> 0
  | _, [] -> 0
  | a :: p, b :: q ->
      if a = b then 1 + longueur_naive p q
      else max (longueur_naive p y) (longueur_naive x q)

(* Programmation dynamique : la même récurrence, mais chaque case du
   tableau n'est calculée qu'une fois.  s.(i).(j) est la longueur pour les
   i premiers éléments de x et les j premiers de y. *)
let table x y =
  let m = Array.length x and n = Array.length y in
  let s = Array.make_matrix (m + 1) (n + 1) 0 in
  for i = 1 to m do
    for j = 1 to n do
      if x.(i - 1) = y.(j - 1) then s.(i).(j) <- s.(i - 1).(j - 1) + 1
      else s.(i).(j) <- max s.(i - 1).(j) s.(i).(j - 1)
    done
  done;
  s

let longueur x y =
  let s = table x y in
  s.(Array.length x).(Array.length y)

(* Reconstruction : on relit la table depuis le coin, en remontant par le
   choix qui a produit chaque case. *)
let temoin x y =
  let s = table x y in
  let i = ref (Array.length x) and j = ref (Array.length y) in
  let sortie = ref [] in
  while !i > 0 && !j > 0 do
    if x.(!i - 1) = y.(!j - 1) then begin
      sortie := x.(!i - 1) :: !sortie;
      decr i;
      decr j
    end
    else if s.(!i - 1).(!j) >= s.(!i).(!j - 1) then decr i
    else decr j
  done;
  !sortie

let affiche l =
  List.iter
    (fun v ->
      print_int v;
      print_char ' ')
    l;
  print_newline ()

let () =
  let x = [| 1; 2; 3; 4; 1; 2; 3 |] and y = [| 2; 4; 3; 1; 2; 1 |] in
  print_int (longueur_naive (Array.to_list x) (Array.to_list y));
  print_char ' ';
  print_int (longueur x y);
  print_newline ();
  let t = temoin x y in
  affiche t;
  print_int (List.length t);
  print_char ' ';
  print_string (if est_sous_suite t (Array.to_list x) then "oui" else "non");
  print_char ' ';
  print_string (if est_sous_suite t (Array.to_list y) then "oui" else "non");
  print_char ' ';
  affiche (prefixe 3 (Array.to_list x))
