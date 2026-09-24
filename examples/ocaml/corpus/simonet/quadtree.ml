(* Quadtrees et calcul de forces.  D'après le TP 8 de Vincent Simonet (MP,
   2003) : la méthode de Barnes et Hut pour le problème à n corps.

   Le calcul direct des forces coûte n^2.  L'idée est qu'un amas de corps
   lointain agit à peu près comme un seul corps placé à leur centre de
   masse : on range les corps dans un arbre quaternaire, chaque cellule
   retient la masse et le centre de masse de ce qu'elle contient, et on
   s'arrête de descendre dès que la cellule est assez loin.

   Les résultats sont affichés en millièmes, pour ne dépendre d'aucune
   convention d'écriture des flottants. *)

type vecteur = { vx : float; vy : float }

let plus a b = { vx = a.vx +. b.vx; vy = a.vy +. b.vy }
let moins a b = { vx = a.vx -. b.vx; vy = a.vy -. b.vy }
let fois k a = { vx = k *. a.vx; vy = k *. a.vy }
let norme a = sqrt ((a.vx *. a.vx) +. (a.vy *. a.vy))

type corps = { masse : float; position : vecteur }

(* Une cellule couvre un carré, et retient la masse et le centre de masse
   de tout ce qui s'y trouve.  Ses quatre filles sont ses quadrants. *)
type arbre = Vide | Feuille of corps | Noeud of cellule

and cellule = {
  mutable m : float;
  mutable centre : vecteur;
  coin : vecteur;
  cote : float;
  filles : arbre array;
}

(* Le quadrant d'un point dans une cellule : deux comparaisons, deux bits. *)
let quadrant c p =
  let milieu_x = c.coin.vx +. (c.cote /. 2.0)
  and milieu_y = c.coin.vy +. (c.cote /. 2.0) in
  (if p.vx < milieu_x then 0 else 1) + (if p.vy < milieu_y then 0 else 2)

let cellule_vide coin cote =
  {
    m = 0.0;
    centre = { vx = 0.0; vy = 0.0 };
    coin;
    cote;
    filles = Array.make 4 Vide;
  }

let coin_fille c i =
  let demi = c.cote /. 2.0 in
  {
    vx = c.coin.vx +. (if i mod 2 = 0 then 0.0 else demi);
    vy = c.coin.vy +. (if i < 2 then 0.0 else demi);
  }

(* L'insertion.  Tomber sur une feuille oblige à subdiviser, et à replacer
   le corps qui s'y trouvait déjà.  Deux corps exactement au même point
   feraient subdiviser sans fin : un vrai code les traite à part. *)
let rec insere a b coin cote =
  match a with
  | Vide -> Feuille b
  | Feuille ancien ->
      let c = cellule_vide coin cote in
      place c ancien;
      place c b;
      Noeud c
  | Noeud c ->
      place c b;
      a

and place c b =
  let i = quadrant c b.position in
  c.filles.(i) <- insere c.filles.(i) b (coin_fille c i) (c.cote /. 2.0)

let arbre_univers corps coin cote =
  List.fold_left (fun a b -> insere a b coin cote) Vide corps

(* Les masses et centres de masse, calculés une fois pour toutes en
   remontant : c'est ce qui rend le parcours suivant bon marché. *)
let rec resume a =
  match a with
  | Vide -> (0.0, { vx = 0.0; vy = 0.0 })
  | Feuille b -> (b.masse, b.position)
  | Noeud c ->
      let masse = ref 0.0 and somme = ref { vx = 0.0; vy = 0.0 } in
      Array.iter
        (fun f ->
          let mf, pf = resume f in
          masse := !masse +. mf;
          somme := plus !somme (fois mf pf))
        c.filles;
      c.m <- !masse;
      c.centre <- (if !masse = 0.0 then c.centre else fois (1.0 /. !masse) !somme);
      (c.m, c.centre)

(* La force newtonienne exercée par un corps de masse m placé en q sur un
   corps placé en p, avec G = 1. *)
let attraction p m q =
  let d = moins q p in
  let r = norme d in
  if r = 0.0 then { vx = 0.0; vy = 0.0 } else fois (m /. (r *. r *. r)) d

(* Le critère de Barnes et Hut : on remplace une cellule par son centre de
   masse dès que son côté vu depuis p est plus petit que theta. *)
let rec force theta a p =
  match a with
  | Vide -> { vx = 0.0; vy = 0.0 }
  | Feuille b -> attraction p b.masse b.position
  | Noeud c ->
      let r = norme (moins c.centre p) in
      if r > 0.0 && c.cote /. r < theta then attraction p c.m c.centre
      else
        Array.fold_left (fun acc f -> plus acc (force theta f p)) { vx = 0.0; vy = 0.0 }
          c.filles

(* Le calcul direct, qui sert d'étalon. *)
let force_directe corps p =
  List.fold_left
    (fun acc b -> plus acc (attraction p b.masse b.position))
    { vx = 0.0; vy = 0.0 } corps

let milliemes v = truncate (v *. 1000.0)

let affiche v =
  print_int (milliemes v.vx);
  print_char ' ';
  print_int (milliemes v.vy);
  print_newline ()

let () =
  let corps =
    [
      { masse = 1.0; position = { vx = 1.0; vy = 1.0 } };
      { masse = 2.0; position = { vx = 3.0; vy = 1.0 } };
      { masse = 1.0; position = { vx = 7.0; vy = 7.0 } };
      { masse = 4.0; position = { vx = 7.5; vy = 7.5 } };
    ]
  in
  let coin = { vx = 0.0; vy = 0.0 } in
  let a = arbre_univers corps coin 8.0 in
  let m, centre = resume a in
  print_int (milliemes m);
  print_char ' ';
  affiche centre;
  let p = { vx = 0.5; vy = 0.5 } in
  affiche (force_directe corps p);
  (* Avec theta nul on ne coupe jamais : le résultat doit être le même. *)
  affiche (force 0.0 a p);
  (* Avec theta = 1, l'amas lointain compte pour un seul corps, et
     l'écart avec le calcul direct est sous le millième. *)
  affiche (force 1.0 a p);
  (* Avec theta = 2, tout l'univers compte pour un seul corps : rapide,
     et faux. *)
  affiche (force 2.0 a p);
  print_int (quadrant (cellule_vide coin 8.0) { vx = 1.0; vy = 5.0 });
  print_char ' ';
  print_int (quadrant (cellule_vide coin 8.0) { vx = 5.0; vy = 5.0 });
  print_newline ()
