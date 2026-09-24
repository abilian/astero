(* Dictionnaires par listes d'association : le chapitre sans Hashtbl. *)

exception Absent

let rec cherche cle d =
  match d with
  | [] -> raise Absent
  | (k, v) :: q -> if k = cle then v else cherche cle q

let rec present cle d =
  match d with [] -> false | (k, _) :: q -> k = cle || present cle q

let rec ajoute cle valeur d =
  match d with
  | [] -> [ (cle, valeur) ]
  | (k, v) :: q ->
      if k = cle then (cle, valeur) :: q else (k, v) :: ajoute cle valeur q

let rec supprime cle d =
  match d with
  | [] -> []
  | (k, v) :: q -> if k = cle then q else (k, v) :: supprime cle q

let cles d = List.map fst d
let valeurs d = List.map snd d
let taille d = List.length d

let occurrences l =
  let compte d x = if present x d then ajoute x (cherche x d + 1) d else ajoute x 1 d in
  List.fold_left compte [] l

let trouve_defaut cle defaut d = try cherche cle d with Absent -> defaut

let () =
  let d = ajoute 2 20 (ajoute 1 10 []) in
  print_int (cherche 1 d);
  print_char ' ';
  print_int (trouve_defaut 9 0 d);
  print_char ' ';
  print_int (taille (supprime 1 d));
  print_newline ();
  let compte = occurrences [ 1; 2; 1; 3; 1; 2 ] in
  print_int (cherche 1 compte);
  print_int (cherche 2 compte);
  print_int (cherche 3 compte);
  print_newline ();
  List.iter print_int (List.rev (cles compte))
