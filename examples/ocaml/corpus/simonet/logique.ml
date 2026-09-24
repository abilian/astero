(* Un peu de logique.  D'après le TP 10 de Vincent Simonet (MPSI, 2001 et
   2002) : un type d'expressions logiques, une recherche exhaustive de
   modèle, puis trois énigmes que l'on résout en les traduisant. *)

type expr =
  | Zero
  | Un
  | Var of int
  | Non of expr
  | Ou of expr * expr
  | Et of expr * expr
  | Oux of expr * expr
  | Implique of expr * expr
  | Equivaut of expr * expr

(* Un environnement est un tableau de booléens : g.(i) est la valeur de la
   variable x_i. *)
let rec evalue e g =
  match e with
  | Zero -> false
  | Un -> true
  | Var i -> g.(i)
  | Non a -> not (evalue a g)
  | Ou (a, b) -> evalue a g || evalue b g
  | Et (a, b) -> evalue a g && evalue b g
  | Oux (a, b) -> evalue a g <> evalue b g
  | Implique (a, b) -> (not (evalue a g)) || evalue b g
  | Equivaut (a, b) -> evalue a g = evalue b g

let rec indice_max e =
  match e with
  | Zero | Un -> -1
  | Var i -> i
  | Non a -> indice_max a
  | Ou (a, b) | Et (a, b) | Oux (a, b) | Implique (a, b) | Equivaut (a, b) ->
      max (indice_max a) (indice_max b)

exception Deborde
exception Insatisfiable

(* L'environnement suivant dans l'ordre lexicographique, en place : c'est
   l'addition binaire, et la retenue qui sort du tableau déborde. *)
let incremente g =
  let i = ref (Array.length g - 1) in
  while !i >= 0 && g.(!i) do
    g.(!i) <- false;
    decr i
  done;
  if !i < 0 then raise Deborde;
  g.(!i) <- true

(* Recherche exhaustive : 2^n environnements, donc un coût exponentiel en
   le nombre de variables. *)
let satisfait e =
  let g = Array.make (indice_max e + 1) false in
  let fini = ref false and trouve = ref false in
  while not !fini do
    if evalue e g then begin
      trouve := true;
      fini := true
    end
    else begin
      try incremente g with Deborde -> fini := true
    end
  done;
  if !trouve then g else raise Insatisfiable

(* Une tautologie est une expression dont la négation n'est pas
   satisfiable.  On rend un contre-exemple s'il y en a un. *)
let tautologie e = try Some (satisfait (Non e)) with Insatisfiable -> None

let affiche g =
  Array.iter (fun v -> print_char (if v then '1' else '0')) g;
  print_newline ()

let resout nom e =
  print_string nom;
  print_char ' ';
  try affiche (satisfait e) with Insatisfiable -> print_endline "impossible"

(* Deux combinateurs, pour écrire les énigmes sans les développer. *)
let rec au_moins_deux l =
  match l with
  | [] | [ _ ] -> Zero
  | t :: q -> Ou (Et (t, Ou (Ou (Zero, Zero), List.fold_left (fun a b -> Ou (a, b)) Zero q)), au_moins_deux q)

let exactement_un l =
  let un_au_moins = List.fold_left (fun a b -> Ou (a, b)) Zero l in
  let deux = au_moins_deux l in
  Et (un_au_moins, Non deux)

let () =
  (* Une tautologie, et une expression qui n'en est pas une. *)
  print_string
    (match tautologie (Ou (Var 0, Non (Var 0))) with
    | None -> "tautologie"
    | Some _ -> "non");
  print_char ' ';
  print_string
    (match tautologie (Implique (Var 0, Var 1)) with
    | None -> "tautologie"
    | Some _ -> "non");
  print_newline ();

  (* L'Île aux questions.  Un positif ne pose que des questions dont la
     réponse est oui, un négatif que des questions dont la réponse est
     non.  x_0 : A est positif ; x_1 : B est positif.  A demande « l'un
     de nous est-il négatif ? ». *)
  resout "ile" (Equivaut (Var 0, Ou (Non (Var 0), Non (Var 1))));

  (* Enquête.  x_0, x_1, x_2 : A, B, C sont coupables.  Au moins un l'est ;
     si A est coupable il a au plus un complice ; si B est innocent C
     l'est aussi, et réciproquement ; si exactement deux sont coupables,
     A en fait partie. *)
  let a = Var 0 and b = Var 1 and c = Var 2 in
  let deux_exactement =
    Ou (Ou (Et (Et (a, b), Non c), Et (Et (a, c), Non b)), Et (Et (b, c), Non a))
  in
  resout "enquete"
    (Et
       ( Et
           ( Et (Ou (Ou (a, b), c), Implique (a, Non (Et (b, c)))),
             Et (Implique (Non b, Non c), Implique (Non c, Non b)) ),
         Implique (deux_exactement, a) ));

  (* Trois coffrets.  x_0, x_1, x_2 : l'or, le plomb, l'argent sont gravés
     par Bellini, qui n'écrit que des vérités ; Cellini n'écrit que des
     mensonges.  x_3, x_4, x_5 : le portrait est dans l'or, le plomb,
     l'argent.  Or et argent disent « le portrait est ici », le plomb dit
     « au moins deux coffrets sont de Cellini ». *)
  let or_ = Var 0 and plomb = Var 1 and argent = Var 2 in
  resout "coffrets"
    (Et
       ( Et
           ( Equivaut (or_, Var 3),
             Equivaut (plomb, au_moins_deux [ Non or_; Non plomb; Non argent ])
           ),
         Et (Equivaut (argent, Var 5), exactement_un [ Var 3; Var 4; Var 5 ]) ))
