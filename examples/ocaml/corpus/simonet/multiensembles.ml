(* Multi-ensembles.  D'après le TP 2 de Vincent Simonet (MPSI, 2002) : un
   multi-ensemble est un ensemble où chaque élément a un ordre de
   multiplicité.  On le représente par une liste, dont l'ordre ne compte
   pas mais dont les répétitions comptent. *)

(* Ensembles.  La représentation par liste est surjective et non
   injective : plusieurs listes décrivent le même ensemble. *)
let rec appartient x e =
  match e with [] -> false | t :: q -> t = x || appartient x q

let rec union e f =
  match e with [] -> f | t :: q -> if appartient t f then union q f else t :: union q f

let rec intersection e f =
  match e with
  | [] -> []
  | t :: q -> if appartient t f then t :: intersection q f else intersection q f

let rec difference e f =
  match e with
  | [] -> []
  | t :: q -> if appartient t f then difference q f else t :: difference q f

let rec cardinal e =
  match e with
  | [] -> 0
  | t :: q -> if appartient t q then cardinal q else 1 + cardinal q

(* Multi-ensembles.  La multiplicité remplace l'appartenance. *)
let rec multiplicite x m =
  match m with [] -> 0 | t :: q -> (if t = x then 1 else 0) + multiplicite x q

(* Une seule occurrence retirée, contrairement à la différence des
   ensembles qui les retire toutes. *)
let rec retire x m =
  match m with
  | [] -> []
  | t :: q -> if t = x then q else t :: retire x q

(* La somme concatène : les multiplicités s'ajoutent. *)
let somme_m m n = m @ n

(* La différence retranche les multiplicités, sans descendre sous zéro. *)
let rec difference_m m n =
  match n with [] -> m | t :: q -> difference_m (retire t m) q

(* Pour l'union, la multiplicité est le maximum : on garde tout m et on y
   ajoute ce que n a en trop. *)
let union_m m n = somme_m m (difference_m n m)

(* Pour l'intersection, c'est le minimum : chaque élément de m consomme
   une occurrence de n. *)
let rec intersection_m m n =
  match m with
  | [] -> []
  | t :: q ->
      if appartient t n then t :: intersection_m q (retire t n) else intersection_m q n

(* Représentant canonique : la liste triée, obtenue par insertion. *)
let rec insere x m =
  match m with [] -> [ x ] | t :: q -> if x <= t then x :: m else t :: insere x q

let rec canonique m = match m with [] -> [] | t :: q -> insere t (canonique q)

let affiche m =
  print_char '{';
  List.iter
    (fun v ->
      print_int v;
      print_char ' ')
    m;
  print_char '}'

let () =
  let e = [ 5; 9; 5 ] and f = [ 9; 7 ] in
  print_int (cardinal e);
  print_char ' ';
  affiche (union e f);
  affiche (intersection e f);
  affiche (difference e f);
  print_newline ();
  let m = [ 0; 0; 1; 2 ] and n = [ 0; 2; 2; 2 ] in
  print_int (multiplicite 2 n);
  print_char ' ';
  affiche (canonique (somme_m m n));
  affiche (canonique (union_m m n));
  affiche (canonique (intersection_m m n));
  affiche (canonique (difference_m m n));
  print_newline ();
  affiche (canonique [ 3; 1; 4; 1; 5; 9; 2; 6 ]);
  print_newline ()
