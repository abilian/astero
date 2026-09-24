(* Rendu de monnaie.  D'après le TP 8 de Vincent Simonet (MPSI, 2002),
   lui-même tiré de Centrale-Supélec 2002 : rendre une somme avec le moins
   de pièces possible.

   Un système est la liste des valeurs faciales, strictement décroissante
   et terminée par 1.  L'algorithme glouton, qui prend toujours la plus
   grosse pièce possible, n'est pas toujours optimal : un système où il
   l'est est dit canonique, et Kozen et Zaks donnent de quoi le décider. *)

let rec est_un_systeme c =
  match c with
  | [] -> false
  | [ x ] -> x = 1
  | x :: (y :: _ as q) -> x > y && est_un_systeme q

(* Les poids minimaux M(y) pour y de 0 à x, par programmation dynamique :
   M(y) vaut 1 de plus que le meilleur M(y - c_i). *)
let poids_minimaux x c =
  let m = Array.make (x + 1) 0 in
  for y = 1 to x do
    let meilleur = ref (y + 1) in
    List.iter (fun v -> if v <= y then meilleur := min !meilleur (1 + m.(y - v))) c;
    m.(y) <- !meilleur
  done;
  m

let minimal x c = (poids_minimaux x c).(x)

(* L'algorithme glouton : autant de la plus grosse pièce que possible,
   puis on recommence avec le reste du système. *)
let rec glouton x c =
  match c with
  | [] -> []
  | v :: q ->
      let k = x / v in
      k :: glouton (x - (k * v)) q

let poids k = List.fold_left (fun a b -> a + b) 0 k

(* Le plus petit contre-éventuel est à chercher entre c_{m-2} + 2 et
   c_1 + c_2 - 1 : en deçà le glouton est optimal, au-delà il l'est aussi
   dès qu'il l'est plus bas. *)
let bornes c =
  match c with
  | c1 :: c2 :: _ ->
      let rec avant_dernier l =
        match l with [ x; _ ] -> x | _ :: q -> avant_dernier q | [] -> 1
      in
      (avant_dernier c + 2, c1 + c2 - 1)
  | _ -> (1, 0)

let contre_exemple c =
  let bas, haut = bornes c in
  let m = poids_minimaux haut c in
  let trouve = ref 0 in
  for x = haut downto bas do
    if m.(x) < poids (glouton x c) then trouve := x
  done;
  !trouve

let est_canonique c = contre_exemple c = 0

let affiche k =
  print_char '[';
  List.iter
    (fun v ->
      print_int v;
      print_char ' ')
    k;
  print_char ']'

let () =
  List.iter
    (fun c ->
      print_string (if est_un_systeme c then "oui " else "non "))
    [ [ 5; 2; 1 ]; [ 5; 7; 1 ]; [ 7; 5; 2 ]; [ 1 ] ];
  print_newline ();
  let euro = [ 200; 100; 50; 20; 10; 5; 2; 1 ] in
  affiche (glouton 287 euro);
  print_int (poids (glouton 287 euro));
  print_char ' ';
  print_int (minimal 287 euro);
  print_newline ();
  (* Le système (10, 5, 2, 1) décompose 27 en 10 + 10 + 5 + 2. *)
  affiche (glouton 27 [ 10; 5; 2; 1 ]);
  print_newline ();
  (* Les poids minimaux dans (4, 3, 1), pour y de 0 à 8. *)
  Array.iter
    (fun v ->
      print_int v;
      print_char ' ')
    (poids_minimaux 8 [ 4; 3; 1 ]);
  print_newline ();
  List.iter
    (fun c ->
      affiche c;
      print_char ' ';
      print_string (if est_canonique c then "canonique" else "contre-exemple ");
      if not (est_canonique c) then print_int (contre_exemple c);
      print_newline ())
    [ euro; [ 4; 3; 1 ]; [ 5; 4; 1 ]; [ 10; 5; 2; 1 ]; [ 6; 3; 1 ] ]
