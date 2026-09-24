(* Commutation d'interrupteurs.  D'après le TP 6 de Vincent Simonet (MPSI,
   2001 et MP, 2003), lui-même tiré du concours de Polytechnique 2000.

   Un tableau de bord porte N interrupteurs, chacun levé ou baissé.  On
   veut essayer les 2^N configurations, et le coût est le nombre de
   commutations.  Une configuration est la partie des indices baissés, et
   une partie est la liste croissante de ses indices. *)

let rec card p = match p with [] -> 0 | _ :: q -> 1 + card q

(* Différence symétrique, par fusion des deux listes croissantes : ce sont
   exactement les interrupteurs à commuter pour passer de p à q. *)
let rec delta p q =
  match (p, q) with
  | [], _ -> q
  | _, [] -> p
  | a :: p', b :: q' ->
      if a = b then delta p' q'
      else if a < b then a :: delta p' q
      else b :: delta p q'

let affiche p =
  List.iter
    (fun i ->
      print_int i;
      print_char ' ')
    p

(* Successeur : la partie q telle que somme des 2^i sur q vaille un de plus
   que sur p.  C'est l'addition binaire, et la retenue s'arrête au premier
   indice absent. *)
let rec depuis i p =
  match p with t :: q when t = i -> depuis (i + 1) q | _ -> i :: p

let succ p = depuis 0 p

(* Toutes les parties de {0, ..., n-1}, dans l'ordre des entiers. *)
let rec parties n p =
  if card p = n then [ p ] else p :: parties n (succ p)

(* Le test complet par incrément : on part tous levés, on parcourt les 2^n
   configurations, et on relève tout à la fin. *)
let test_incremental n =
  let rec commute courante restantes =
    match restantes with
    | [] -> delta courante []
    | suivante :: reste -> delta courante suivante @ commute suivante reste
  in
  commute [] (parties n [])

(* Le code de Gray : T(0) est vide et T(n+1) = T(n), n, T(n).  Chaque terme
   est l'unique interrupteur à commuter, donc le test coûte 2^n - 1. *)
let rec gray n = if n = 0 then [] else gray (n - 1) @ (n - 1) :: gray (n - 1)

(* Les configurations que le code de Gray fait défiler. *)
let configurations n =
  List.fold_left
    (fun vues i ->
      match vues with
      | [] -> [ [ i ] ]
      | derniere :: _ -> delta derniere [ i ] :: vues)
    [ [] ] (gray n)

let () =
  let p = [ 0; 2; 5 ] and q = [ 1; 2; 3 ] in
  print_int (card p);
  print_char ' ';
  affiche (delta p q);
  print_newline ();
  affiche (succ [ 0; 1; 3 ]);
  print_char '|';
  affiche (succ [ 2 ]);
  print_newline ();
  List.iter
    (fun c ->
      print_char '{';
      affiche c;
      print_char '}')
    (parties 3 []);
  print_newline ();
  let t = test_incremental 3 in
  affiche t;
  print_int (List.length t);
  print_newline ();
  affiche (gray 4);
  print_int (List.length (gray 4));
  print_newline ();
  List.iter
    (fun c ->
      print_char '{';
      affiche c;
      print_char '}')
    (List.rev (configurations 3))
