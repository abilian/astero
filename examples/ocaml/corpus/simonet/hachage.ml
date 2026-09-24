(* Tables de hachage.  D'après le TP 1 de Vincent Simonet (MP, 2003) : une
   fonction de hachage envoie une clef sur un indice, et la table range à
   cet indice la liste des couples qui y tombent.

   Il n'y a pas de Hashtbl dans ce sous-ensemble du langage, ce qui tombe
   bien : le sujet est d'en écrire une. *)

(* Hachage des entiers : le reste modulo la taille, ramené au positif. *)
let hache_entier n k = abs k mod n

(* Hachage des chaînes : on combine les caractères par une multiplication
   et une addition, en réduisant à chaque pas pour ne pas déborder. *)
let hache_chaine n s =
  let h = ref 0 in
  for i = 0 to String.length s - 1 do
    h := ((31 * !h) + Char.code s.[i]) mod n
  done;
  !h

(* Table de taille fixe.  La fonction de hachage voyage avec la table :
   c'est elle qui sait comment traiter les clefs. *)
type ('a, 'b) table = { hache : 'a -> int; donnees : ('a * 'b) list array }

let cree hache n = { hache = hache; donnees = Array.make n [] }

let ajoute t clef valeur =
  let i = t.hache clef in
  t.donnees.(i) <- (clef, valeur) :: t.donnees.(i)

let trouve t clef =
  let rec cherche l =
    match l with
    | [] -> raise Not_found
    | (k, v) :: q -> if k = clef then v else cherche q
  in
  cherche t.donnees.(t.hache clef)

let supprime t clef =
  let rec sans l =
    match l with
    | [] -> []
    | (k, v) :: q -> if k = clef then q else (k, v) :: sans q
  in
  let i = t.hache clef in
  t.donnees.(i) <- sans t.donnees.(i)

(* La longueur de la plus longue liste : elle mesure la qualité du
   hachage, puisque c'est le coût du pire accès. *)
let pire t =
  Array.fold_left (fun acc l -> max acc (List.length l)) 0 t.donnees

(* Table de taille dynamique.  La fonction de hachage prend maintenant la
   taille en argument, parce que celle-ci change.  On double dès qu'il y a
   plus d'entrées que de cases : les listes restent courtes. *)
type ('a, 'b) dyntable = {
  hache_d : int -> 'a -> int;
  mutable entrees : int;
  mutable cases : ('a * 'b) list array;
}

let cree_dyn hache n = { hache_d = hache; entrees = 0; cases = Array.make n [] }

let agrandit t =
  let ancien = t.cases in
  let neuf = Array.make (2 * Array.length ancien) [] in
  t.cases <- neuf;
  Array.iter
    (List.iter (fun (k, v) ->
         let i = t.hache_d (Array.length neuf) k in
         neuf.(i) <- (k, v) :: neuf.(i)))
    ancien

let ajoute_dyn t clef valeur =
  if t.entrees >= Array.length t.cases then agrandit t;
  let i = t.hache_d (Array.length t.cases) clef in
  t.cases.(i) <- (clef, valeur) :: t.cases.(i);
  t.entrees <- t.entrees + 1

let trouve_dyn t clef =
  let rec cherche l =
    match l with
    | [] -> raise Not_found
    | (k, v) :: q -> if k = clef then v else cherche q
  in
  cherche t.cases.(t.hache_d (Array.length t.cases) clef)

let () =
  print_int (hache_entier 13 100);
  print_char ' ';
  print_int (hache_entier 13 (-100));
  print_char ' ';
  print_int (hache_chaine 13 "caml");
  print_char ' ';
  print_int (hache_chaine 13 "lmac");
  print_newline ();
  let t = cree (hache_chaine 7) 7 in
  List.iter
    (fun (k, v) -> ajoute t k v)
    [ ("un", 1); ("deux", 2); ("trois", 3); ("quatre", 4); ("cinq", 5) ];
  print_int (trouve t "trois");
  print_char ' ';
  print_int (try trouve t "six" with Not_found -> -1);
  print_char ' ';
  print_int (pire t);
  print_newline ();
  supprime t "trois";
  print_int (try trouve t "trois" with Not_found -> -1);
  print_newline ();
  let d = cree_dyn hache_entier 2 in
  for k = 0 to 9 do
    ajoute_dyn d k (k * k)
  done;
  print_int (Array.length d.cases);
  print_char ' ';
  print_int d.entrees;
  print_char ' ';
  print_int (trouve_dyn d 7);
  print_newline ()
