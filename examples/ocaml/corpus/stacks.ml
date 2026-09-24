(* Piles et files, les deux structures du chapitre. *)

exception Vide

type 'a pile = { mutable contenu : 'a list }

let pile_vide () = { contenu = [] }
let empile p x = p.contenu <- x :: p.contenu
let est_vide p = p.contenu = []
let hauteur p = List.length p.contenu

let depile p =
  match p.contenu with
  | [] -> raise Vide
  | t :: q ->
      p.contenu <- q;
      t

let sommet p = match p.contenu with [] -> raise Vide | t :: _ -> t

(* Une file amortie sur deux piles : on enfile d'un côté, on défile de
   l'autre, et on retourne la première quand la seconde se vide. *)
type 'a file = { mutable entree : 'a list; mutable sortie : 'a list }

let file_vide () = { entree = []; sortie = [] }
let enfile f x = f.entree <- x :: f.entree
let file_est_vide f = f.entree = [] && f.sortie = []

let defile f =
  if f.sortie = [] then begin
    f.sortie <- List.rev f.entree;
    f.entree <- []
  end;
  match f.sortie with
  | [] -> raise Vide
  | t :: q ->
      f.sortie <- q;
      t

let bien_parenthesee s =
  let p = pile_vide () in
  let bon = ref true in
  for i = 0 to String.length s - 1 do
    if s.[i] = '(' then empile p 1
    else if s.[i] = ')' then
      if est_vide p then bon := false else ignore (depile p)
  done;
  !bon && est_vide p

let () =
  let p = pile_vide () in
  empile p 1;
  empile p 2;
  empile p 3;
  print_int (depile p);
  print_int (sommet p);
  print_int (hauteur p);
  print_newline ();
  let f = file_vide () in
  enfile f 1;
  enfile f 2;
  print_int (defile f);
  enfile f 3;
  print_int (defile f);
  print_int (defile f);
  print_newline ();
  print_string (if bien_parenthesee "(()())" then "oui" else "non");
  print_char ' ';
  print_string (if bien_parenthesee "(()" then "oui" else "non")
