(* Arbres rouge et noir.  D'après le TP 4 de Vincent Simonet (MP, 2003).

   Un arbre binaire de recherche dégénère en liste si on l'alimente en
   ordre croissant.  Les arbres rouge et noir gardent la hauteur en
   O(log n) avec deux règles : jamais deux nœuds rouges de suite, et
   autant de nœuds noirs sur tous les chemins de la racine aux feuilles.

   L'insertion peint le nouveau nœud en rouge, ce qui préserve la seconde
   règle, puis répare la première en remontant. *)

type couleur = Rouge | Noir
type 'a arbre = Vide | N of couleur * 'a arbre * 'a * 'a arbre

let rec appartient x a =
  match a with
  | Vide -> false
  | N (_, g, y, d) -> x = y || appartient x (if x < y then g else d)

(* Première règle : aucun nœud rouge n'a de fils rouge. *)
let rec sans_conflit a =
  match a with
  | Vide -> true
  | N (Rouge, N (Rouge, _, _, _), _, _) | N (Rouge, _, _, N (Rouge, _, _, _)) ->
      false
  | N (_, g, _, d) -> sans_conflit g && sans_conflit d

exception Hauteur_noire

(* Seconde règle : la hauteur noire est la même des deux côtés, partout. *)
let rec hauteur_noire a =
  match a with
  | Vide -> 0
  | N (c, g, _, d) ->
      let h = hauteur_noire g in
      if h <> hauteur_noire d then raise Hauteur_noire;
      if c = Noir then h + 1 else h

let equilibre_noir a = try hauteur_noire a > 0 with Hauteur_noire -> false

(* La réparation.  Un grand-père noir avec un fils rouge et un petit-fils
   rouge se réarrange de la même façon dans les quatre configurations, ce
   que l'on écrit en un seul motif à quatre branches.  Chaque branche lie
   les mêmes noms, sans quoi le filtrage n'aurait pas de sens. *)
let equilibre a =
  match a with
  | N (Noir, N (Rouge, N (Rouge, t1, x1, t2), x2, t3), x3, t4)
  | N (Noir, N (Rouge, t1, x1, N (Rouge, t2, x2, t3)), x3, t4)
  | N (Noir, t1, x1, N (Rouge, N (Rouge, t2, x2, t3), x3, t4))
  | N (Noir, t1, x1, N (Rouge, t2, x2, N (Rouge, t3, x3, t4))) ->
      N (Rouge, N (Noir, t1, x1, t2), x2, N (Noir, t3, x3, t4))
  | _ -> a

let insere x a =
  let rec ajoute a =
    match a with
    | Vide -> N (Rouge, Vide, x, Vide)
    | N (c, g, y, d) ->
        if x < y then equilibre (N (c, ajoute g, y, d))
        else if x > y then equilibre (N (c, g, y, ajoute d))
        else a
  in
  (* La racine est toujours noire : c'est ce qui absorbe le dernier
     conflit rouge sans changer la hauteur noire d'un chemin. *)
  match ajoute a with Vide -> Vide | N (_, g, y, d) -> N (Noir, g, y, d)

let de_liste l = List.fold_left (fun a x -> insere x a) Vide l

let rec taille a = match a with Vide -> 0 | N (_, g, _, d) -> 1 + taille g + taille d

let rec hauteur a =
  match a with Vide -> 0 | N (_, g, _, d) -> 1 + max (hauteur g) (hauteur d)

let rec infixe a =
  match a with Vide -> [] | N (_, g, x, d) -> infixe g @ (x :: infixe d)

(* Le même arbre sans les couleurs, pour voir ce qu'elles évitent. *)
let rec insere_sans_couleur x a =
  match a with
  | Vide -> N (Noir, Vide, x, Vide)
  | N (c, g, y, d) ->
      if x < y then N (c, insere_sans_couleur x g, y, d)
      else if x > y then N (c, g, y, insere_sans_couleur x d)
      else a

let () =
  let a = de_liste [ 1; 2; 3; 4; 5; 6; 7; 8; 9; 10 ] in
  print_int (taille a);
  print_char ' ';
  print_int (hauteur a);
  print_char ' ';
  print_int (hauteur_noire a);
  print_newline ();
  print_string (if sans_conflit a then "sain" else "conflit");
  print_char ' ';
  print_string (if equilibre_noir a then "equilibre" else "desequilibre");
  print_newline ();
  List.iter
    (fun x ->
      print_int x;
      print_char ' ')
    (infixe a);
  print_newline ();
  print_string (if appartient 7 a then "oui" else "non");
  print_char ' ';
  print_string (if appartient 11 a then "oui" else "non");
  print_newline ();
  (* Sans les couleurs, dix insertions croissantes donnent une liste. *)
  let b =
    List.fold_left
      (fun t x -> insere_sans_couleur x t)
      Vide [ 1; 2; 3; 4; 5; 6; 7; 8; 9; 10 ]
  in
  print_int (hauteur b);
  print_char ' ';
  print_int (hauteur a);
  print_newline ()
