(* Labyrinthes.  D'après le TP 9 de Vincent Simonet (MPSI, 2001 et 2002) :
   un labyrinthe est une matrice où 0 est un mur et 1 un chemin.  On
   l'affiche, on en sort par un parcours en profondeur avec une pile
   explicite, puis on en engendre un. *)

let affiche_case v = print_char (if v = 0 then '#' else ' ')

let affiche laby =
  Array.iter
    (fun ligne ->
      Array.iter affiche_case ligne;
      print_newline ())
    laby

(* Une pile d'entiers, de taille bornée : c'est tout ce dont le parcours a
   besoin, et cela tient dans un tableau. *)
type pile = { contenu : int array; mutable sommet : int }

exception Pile_vide

let cree_pile n = { contenu = Array.make n 0; sommet = 0 }
let est_vide p = p.sommet = 0

let empile p v =
  p.contenu.(p.sommet) <- v;
  p.sommet <- p.sommet + 1

let depile p =
  if est_vide p then raise Pile_vide;
  p.sommet <- p.sommet - 1;
  p.contenu.(p.sommet)

let sommet p =
  if est_vide p then raise Pile_vide;
  p.contenu.(p.sommet - 1)

(* Les cases sont numérotées i * largeur + j, pour tenir dans la pile. *)
let voisines laby c =
  let largeur = Array.length laby.(0) in
  let i = c / largeur and j = c mod largeur in
  let garde l =
    List.filter
      (fun (a, b) ->
        a >= 0
        && a < Array.length laby
        && b >= 0 && b < largeur
        && laby.(a).(b) = 1)
      l
  in
  List.map
    (fun (a, b) -> (a * largeur) + b)
    (garde [ (i - 1, j); (i, j + 1); (i + 1, j); (i, j - 1) ])

(* Parcours en profondeur.  On marque chaque case en y arrivant, et la
   pile garde le chemin depuis le départ : quand on atteint l'arrivée, il
   suffit de la lire. *)
let sortie laby depart arrivee =
  let hauteur = Array.length laby and largeur = Array.length laby.(0) in
  let vu = Array.make_matrix hauteur largeur false in
  let p = cree_pile (hauteur * largeur) in
  let marque c = vu.(c / largeur).(c mod largeur) <- true in
  empile p depart;
  marque depart;
  let trouve = ref false in
  while (not !trouve) && not (est_vide p) do
    let c = sommet p in
    if c = arrivee then trouve := true
    else
      match
        List.filter
          (fun v -> not vu.(v / largeur).(v mod largeur))
          (voisines laby c)
      with
      | [] -> ignore (depile p)
      | v :: _ ->
          marque v;
          empile p v
  done;
  if not !trouve then raise Not_found;
  Array.to_list (Array.sub p.contenu 0 p.sommet)

(* Génération.  On creuse à partir d'une case sur deux, en abattant le mur
   qui sépare la case courante d'une voisine encore pleine.  Le tirage est
   une suite pseudo-aléatoire, pour que le labyrinthe soit toujours le
   même. *)
let graine = ref 12345
let tire n =
  graine := ((1103515245 * !graine) + 12345) mod 2147483648;
  !graine mod n

let engendre hauteur largeur =
  let laby = Array.make_matrix ((2 * hauteur) + 1) ((2 * largeur) + 1) 0 in
  let vu = Array.make_matrix hauteur largeur false in
  let p = cree_pile (hauteur * largeur) in
  let creuse i j = laby.((2 * i) + 1).((2 * j) + 1) <- 1 in
  empile p 0;
  vu.(0).(0) <- true;
  creuse 0 0;
  while not (est_vide p) do
    let c = sommet p in
    let i = c / largeur and j = c mod largeur in
    let libres =
      List.filter
        (fun (a, b) ->
          a >= 0 && a < hauteur && b >= 0 && b < largeur && not vu.(a).(b))
        [ (i - 1, j); (i, j + 1); (i + 1, j); (i, j - 1) ]
    in
    match libres with
    | [] -> ignore (depile p)
    | _ ->
        let a, b = List.nth libres (tire (List.length libres)) in
        vu.(a).(b) <- true;
        creuse a b;
        laby.(i + a + 1).(j + b + 1) <- 1;
        empile p ((a * largeur) + b)
  done;
  laby

let () =
  let laby =
    [|
      [| 0; 0; 0; 0; 0; 0; 0 |];
      [| 0; 1; 1; 1; 0; 1; 0 |];
      [| 0; 1; 0; 1; 0; 1; 0 |];
      [| 0; 1; 0; 1; 1; 1; 0 |];
      [| 0; 1; 0; 0; 0; 1; 0 |];
      [| 0; 1; 1; 1; 1; 1; 0 |];
      [| 0; 0; 0; 0; 0; 0; 0 |];
    |]
  in
  affiche laby;
  let chemin = sortie laby ((1 * 7) + 1) ((1 * 7) + 5) in
  print_int (List.length chemin);
  print_char ':';
  List.iter
    (fun c ->
      print_char ' ';
      print_int (c / 7);
      print_char ',';
      print_int (c mod 7))
    chemin;
  print_newline ();
  affiche (engendre 4 6)
