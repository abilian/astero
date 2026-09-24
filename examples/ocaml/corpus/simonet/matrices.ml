(* Multiplication d'une suite de matrices.  D'après le TP 5 de Vincent
   Simonet (MP, 2003), seconde partie.

   Le produit A_0 A_1 ... A_{n-1} est associatif, mais le nombre de
   multiplications scalaires dépend du parenthésage.  Si A_i est de taille
   d.(i) x d.(i+1), multiplier deux blocs coûte le produit des trois
   dimensions concernées, et il faut choisir où couper.

   C'est la même récurrence que la plus longue sous-suite commune : on la
   calcule une fois par case, en remontant par les longueurs. *)

type arbre = Matrice of int | Produit of arbre * arbre

exception Trop_court

(* s.(i).(j) est le coût minimal du produit A_i ... A_{j-1}, et coupe le
   point où le meilleur parenthésage sépare ce bloc en deux. *)
let couts d =
  let n = Array.length d - 1 in
  if n < 1 then raise Trop_court;
  let s = Array.make_matrix (n + 1) (n + 1) 0 in
  let coupe = Array.make_matrix (n + 1) (n + 1) 0 in
  for longueur = 2 to n do
    for i = 0 to n - longueur do
      let j = i + longueur in
      s.(i).(j) <- -1;
      for k = i + 1 to j - 1 do
        let essai = s.(i).(k) + s.(k).(j) + (d.(i) * d.(k) * d.(j)) in
        if s.(i).(j) < 0 || essai < s.(i).(j) then begin
          s.(i).(j) <- essai;
          coupe.(i).(j) <- k
        end
      done
    done
  done;
  (s, coupe)

let cout d =
  let s, _ = couts d in
  s.(0).(Array.length d - 1)

(* Le parenthésage lui-même, lu dans la table des coupures. *)
let parenthese d =
  let _, coupe = couts d in
  let rec construit i j =
    if j - i = 1 then Matrice i
    else Produit (construit i coupe.(i).(j), construit coupe.(i).(j) j)
  in
  construit 0 (Array.length d - 1)

let rec affiche a =
  match a with
  | Matrice i ->
      print_char 'A';
      print_int i
  | Produit (g, d) ->
      print_char '(';
      affiche g;
      affiche d;
      print_char ')'

(* Les coûts des deux parenthésages évidents, pour comparer. *)
let cout_gauche d =
  let total = ref 0 in
  for i = 1 to Array.length d - 2 do
    total := !total + (d.(0) * d.(i) * d.(i + 1))
  done;
  !total

let cout_droite d =
  let n = Array.length d - 1 in
  let total = ref 0 in
  for i = n - 1 downto 1 do
    total := !total + (d.(i - 1) * d.(i) * d.(n))
  done;
  !total

let () =
  (* Quatre matrices : 10x100, 100x5, 5x50, 50x1. *)
  let d = [| 10; 100; 5; 50; 1 |] in
  print_int (cout d);
  print_char ' ';
  print_int (cout_gauche d);
  print_newline ();
  affiche (parenthese d);
  print_newline ();
  (* Trois matrices, deux parenthésages seulement, et un rapport de dix
     entre les deux coûts. *)
  let e = [| 10; 100; 5; 50 |] in
  print_int (cout e);
  print_char ' ';
  print_int (cout_gauche e);
  print_char ' ';
  print_int (cout_droite e);
  print_newline ();
  affiche (parenthese e);
  print_newline ();
  let f = [| 30; 35; 15; 5; 10; 20; 25 |] in
  print_int (cout f);
  print_newline ();
  affiche (parenthese f);
  print_newline ()
