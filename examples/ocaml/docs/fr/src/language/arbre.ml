type 'a arbre =
  | Feuille
  | Noeud of 'a arbre * 'a * 'a arbre

let rec hauteur a =
  match a with
  | Feuille -> 0
  | Noeud (g, _, d) -> 1 + max (hauteur g) (hauteur d)
