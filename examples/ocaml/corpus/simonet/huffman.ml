(* Arbres binaires et codage de Huffman.  D'après le TP 6 de Vincent
   Simonet (MPSI, 2002) : un arbre binaire étiqueté aux feuilles donne un
   code de longueur variable, et l'arbre de Huffman est celui qui minimise
   la longueur totale du texte codé.

   Le code est préfixe : aucun mot n'est le début d'un autre, parce que
   les lettres sont aux feuilles.  Le décodage est donc sans ambiguïté. *)

type arbre = Feuille of char | Noeud of arbre * arbre

let rec feuilles a =
  match a with Feuille c -> [ c ] | Noeud (g, d) -> feuilles g @ feuilles d

(* Un mot binaire est une liste de 0 et de 1 : à gauche 0, à droite 1. *)
exception Mot_incomplet

let decode a mot =
  let rec descend courant reste =
    match (courant, reste) with
    | Feuille c, _ -> (c, reste)
    | Noeud (_, _), [] -> raise Mot_incomplet
    | Noeud (g, d), b :: q -> descend (if b = 0 then g else d) q
  in
  let rec tout reste =
    if reste = [] then []
    else
      let c, suite = descend a reste in
      c :: tout suite
  in
  tout mot

(* Le code d'une lettre, lu en descendant l'arbre jusqu'à elle. *)
let rec code a c =
  match a with
  | Feuille x -> if x = c then Some [] else None
  | Noeud (g, d) -> (
      match code g c with
      | Some m -> Some (0 :: m)
      | None -> (
          match code d c with Some m -> Some (1 :: m) | None -> None))

exception Absente

let encode a texte =
  let mot = ref [] in
  for i = String.length texte - 1 downto 0 do
    match code a texte.[i] with
    | None -> raise Absente
    | Some m -> mot := m @ !mot
  done;
  !mot

(* Les fréquences des caractères d'un texte. *)
let frequences texte =
  let compte = Array.make 256 0 in
  for i = 0 to String.length texte - 1 do
    let k = Char.code texte.[i] in
    compte.(k) <- compte.(k) + 1
  done;
  let l = ref [] in
  for k = 255 downto 0 do
    if compte.(k) > 0 then l := (compte.(k), Feuille (Char.chr k)) :: !l
  done;
  !l

(* La construction : on fusionne les deux arbres les plus légers jusqu'à
   n'en avoir plus qu'un.  On garde la liste triée, ce qui met les deux
   plus légers en tête. *)
let rec insere x l =
  match l with
  | [] -> [ x ]
  | t :: q -> if fst x <= fst t then x :: l else t :: insere x q

let rec construit l =
  match l with
  | [] -> raise Absente
  | [ (_, a) ] -> a
  | (p, a) :: (q, b) :: reste -> construit (insere (p + q, Noeud (a, b)) reste)

let huffman texte =
  construit (List.fold_left (fun acc x -> insere x acc) [] (frequences texte))

let affiche_mot m =
  List.iter print_int m;
  print_newline ()

let () =
  let texte = "abracadabra" in
  let a = huffman texte in
  List.iter print_char (feuilles a);
  print_newline ();
  List.iter
    (fun c ->
      print_char c;
      print_char ':';
      (match code a c with
      | None -> print_char '?'
      | Some m -> List.iter print_int m);
      print_char ' ')
    [ 'a'; 'b'; 'c'; 'd'; 'r' ];
  print_newline ();
  let m = encode a texte in
  affiche_mot m;
  print_int (List.length m);
  print_char ' ';
  print_int (8 * String.length texte);
  print_newline ();
  let rendu = decode a m in
  List.iter print_char rendu;
  print_char ' ';
  print_string
    (if String.concat "" (List.map (String.make 1) rendu) = texte then "identique"
     else "different");
  print_newline ()
