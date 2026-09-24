(* Arbres binaires de recherche.  D'après le TP 8 de Vincent Simonet
   (MPSI, 2001) : les arbres binaires et leurs mesures, puis la propriété
   qui en fait des arbres de recherche, puis les tables d'association. *)

type 'a arbre = Vide | Noeud of 'a arbre * 'a * 'a arbre

let rec taille a =
  match a with Vide -> 0 | Noeud (g, _, d) -> 1 + taille g + taille d

let rec hauteur a =
  match a with Vide -> 0 | Noeud (g, _, d) -> 1 + max (hauteur g) (hauteur d)

exception Arbre_vide

(* Le maximum d'un arbre quelconque : il faut visiter tous les nœuds. *)
let rec maximum a =
  match a with
  | Vide -> raise Arbre_vide
  | Noeud (Vide, x, Vide) -> x
  | Noeud (Vide, x, d) -> max x (maximum d)
  | Noeud (g, x, Vide) -> max x (maximum g)
  | Noeud (g, x, d) -> max x (max (maximum g) (maximum d))

(* Le parcours infixe rend les étiquettes de gauche à droite. *)
let rec infixe a =
  match a with Vide -> [] | Noeud (g, x, d) -> infixe g @ (x :: infixe d)

(* Un arbre est de recherche si son parcours infixe est croissant. *)
let est_abr a =
  let rec croissante l =
    match l with x :: (y :: _ as q) -> x < y && croissante q | _ -> true
  in
  croissante (infixe a)

(* Dans un arbre de recherche, la comparaison dit de quel côté descendre :
   une recherche coûte la hauteur, pas la taille. *)
let rec appartient x a =
  match a with
  | Vide -> false
  | Noeud (g, y, d) ->
      if x = y then true else if x < y then appartient x g else appartient x d

let rec insere x a =
  match a with
  | Vide -> Noeud (Vide, x, Vide)
  | Noeud (g, y, d) ->
      if x = y then a
      else if x < y then Noeud (insere x g, y, d)
      else Noeud (g, y, insere x d)

let rec minimum a =
  match a with
  | Vide -> raise Arbre_vide
  | Noeud (Vide, x, _) -> x
  | Noeud (g, _, _) -> minimum g

(* Supprimer un nœud à deux fils : on le remplace par le plus petit du
   sous-arbre droit, qui n'en a pas moins d'un. *)
let rec supprime x a =
  match a with
  | Vide -> Vide
  | Noeud (g, y, d) ->
      if x < y then Noeud (supprime x g, y, d)
      else if x > y then Noeud (g, y, supprime x d)
      else (
        match (g, d) with
        | Vide, _ -> d
        | _, Vide -> g
        | _, _ ->
            let m = minimum d in
            Noeud (g, m, supprime m d))

let de_liste l = List.fold_left (fun a x -> insere x a) Vide l

(* Tables d'association : le même arbre, sur des couples ordonnés par leur
   clef.  L'égalité structurelle sur les couples ne convient pas ici, donc
   les fonctions sont réécrites sur la clef seule. *)
type ('a, 'b) table = Feuille | Entree of ('a, 'b) table * 'a * 'b * ('a, 'b) table

let rec associe clef t =
  match t with
  | Feuille -> raise Not_found
  | Entree (g, k, v, d) ->
      if clef = k then v else if clef < k then associe clef g else associe clef d

let rec ajoute clef valeur t =
  match t with
  | Feuille -> Entree (Feuille, clef, valeur, Feuille)
  | Entree (g, k, v, d) ->
      if clef = k then Entree (g, k, valeur, d)
      else if clef < k then Entree (ajoute clef valeur g, k, v, d)
      else Entree (g, k, v, ajoute clef valeur d)

let affiche l =
  List.iter
    (fun v ->
      print_int v;
      print_char ' ')
    l;
  print_newline ()

let () =
  let a = de_liste [ 8; 3; 10; 1; 6; 14; 4; 7; 13 ] in
  print_int (taille a);
  print_char ' ';
  print_int (hauteur a);
  print_char ' ';
  print_int (maximum a);
  print_char ' ';
  print_int (minimum a);
  print_newline ();
  affiche (infixe a);
  print_string (if est_abr a then "abr" else "quelconque");
  print_char ' ';
  print_string
    (if est_abr (Noeud (Noeud (Vide, 5, Vide), 2, Vide)) then "abr"
     else "quelconque");
  print_newline ();
  print_string (if appartient 6 a then "oui" else "non");
  print_char ' ';
  print_string (if appartient 5 a then "oui" else "non");
  print_newline ();
  affiche (infixe (supprime 3 a));
  affiche (infixe (supprime 8 a));
  let t = ajoute "trois" 3 (ajoute "un" 1 (ajoute "deux" 2 Feuille)) in
  print_int (associe "deux" t);
  print_char ' ';
  print_int (associe "trois" t);
  print_char ' ';
  print_int (try associe "quatre" t with Not_found -> -1);
  print_newline ()
