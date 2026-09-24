(* Le jeu de Marienbad.  D'après le TP 4 de Vincent Simonet (MPSI, 2002) :
   plusieurs rangées d'allumettes ; chacun son tour, un joueur en retire
   autant qu'il veut d'une seule rangée ; celui qui prend la dernière a
   perdu ou gagné selon la règle, ici il gagne.

   La stratégie tient dans une seule opération : le « ou exclusif » des
   tailles des rangées.  La position est perdante pour celui qui doit
   jouer exactement quand ce ou exclusif est nul. *)

(* L'écriture binaire, du bit de poids faible au bit de poids fort. *)
let rec binaire n = if n = 0 then [] else (n mod 2) :: binaire (n / 2)

let rec entier b =
  match b with [] -> 0 | t :: q -> t + (2 * entier q)

(* Le ou exclusif bit à bit, écrit à la main : c'est l'addition sans
   retenue.  L'opérateur lxor fait la même chose. *)
let rec ou_exclusif a b =
  match (a, b) with
  | [], _ -> b
  | _, [] -> a
  | x :: p, y :: q -> (if x = y then 0 else 1) :: ou_exclusif p q

let somme_nim rangees =
  Array.fold_left (fun acc n -> entier (ou_exclusif (binaire acc) (binaire n))) 0 rangees

(* Une configuration est perdante pour le joueur qui doit jouer quand la
   somme de Nim est nulle : quoi qu'il fasse, elle cesse de l'être. *)
let perdante rangees = somme_nim rangees = 0

exception Deja_perdu

(* Un coup gagnant, (rangée, nombre d'allumettes).  On cherche une rangée
   que l'on peut ramener à sa valeur ou-exclusif le reste. *)
let coup rangees =
  let s = somme_nim rangees in
  if s = 0 then raise Deja_perdu;
  let choisi = ref (-1) and cible = ref 0 in
  for i = Array.length rangees - 1 downto 0 do
    let vise = entier (ou_exclusif (binaire rangees.(i)) (binaire s)) in
    if vise < rangees.(i) then begin
      choisi := i;
      cible := vise
    end
  done;
  (!choisi, rangees.(!choisi) - !cible)

let joue rangees (i, k) =
  let r = Array.copy rangees in
  r.(i) <- r.(i) - k;
  r

let vide rangees = Array.fold_left (fun acc n -> acc + n) 0 rangees = 0

let affiche rangees =
  Array.iter
    (fun n ->
      print_int n;
      print_char ' ')
    rangees

(* Deux joueurs parfaits : celui qui trouve une position non perdante
   gagne, l'autre ne peut que retarder. *)
let partie depart =
  let r = ref depart and tour = ref 0 in
  while not (vide !r) do
    let i, k =
      if perdante !r then
        (* Aucun coup ne sauve : on prend une allumette là où il y en a. *)
        let j = ref 0 in
        while !r.(!j) = 0 do
          incr j
        done;
        (!j, 1)
      else coup !r
    in
    print_int !tour;
    print_string " retire ";
    print_int k;
    print_string " en ";
    print_int i;
    print_string " -> ";
    r := joue !r (i, k);
    affiche !r;
    print_newline ();
    tour := 1 - !tour
  done;
  1 - !tour

let () =
  List.iter
    (fun n ->
      List.iter print_int (binaire n);
      print_char ' ')
    [ 1; 3; 5; 7 ];
  print_newline ();
  let r = [| 1; 3; 5; 7 |] in
  print_int (somme_nim r);
  print_char ' ';
  print_string (if perdante r then "perdante" else "gagnante");
  print_char ' ';
  print_int (somme_nim [| 1; 2; 3 |]);
  print_char ' ';
  print_string (if perdante [| 1; 2; 3 |] then "perdante" else "gagnante");
  print_newline ();
  let i, k = coup [| 1; 3; 5 |] in
  print_int i;
  print_char ' ';
  print_int k;
  print_newline ();
  let gagnant = partie [| 1; 3; 5 |] in
  print_string "gagnant ";
  print_int gagnant;
  print_newline ()
