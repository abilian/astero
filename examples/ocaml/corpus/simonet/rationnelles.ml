(* Compilation d'expressions rationnelles.  D'après le TP 6 de Vincent
   Simonet (MP, 2003) : d'une expression rationnelle à un automate non
   déterministe par la construction de Thompson, puis à un automate
   déterministe par la construction des sous-ensembles.

   C'est le chemin que prend un moteur d'expressions rationnelles, et
   celui que prend l'analyseur lexical d'un compilateur. *)

type rationnelle =
  | Vide
  | Epsilon
  | Car of char
  | Ou of rationnelle * rationnelle
  | Suite of rationnelle * rationnelle
  | Etoile of rationnelle

(* Un automate non déterministe : des états numérotés, des transitions
   étiquetées, et des transitions spontanées. *)
type afn = {
  nb : int;
  trans : (int * char * int) list;
  eps : (int * int) list;
  debut : int;
  fin : int;
}

(* La construction de Thompson.  Chaque cas crée deux états et raccorde
   les morceaux par des transitions spontanées, donc l'automate a autant
   d'états que l'expression a de nœuds, à un facteur deux près.

   Les états sont numérotés dans l'ordre où on les crée, donc chaque
   `let` doit être séquentiel : deux définitions liées par `and`
   s'évaluent dans un ordre que le langage ne fixe pas. *)
let construit e =
  let n = ref 0 in
  let neuf () =
    let s = !n in
    n := s + 1;
    s
  in
  let trans = ref [] and eps = ref [] in
  let rec aux e =
    match e with
    | Vide ->
        let i = neuf () in
        let f = neuf () in
        (i, f)
    | Epsilon ->
        let i = neuf () in
        let f = neuf () in
        eps := (i, f) :: !eps;
        (i, f)
    | Car c ->
        let i = neuf () in
        let f = neuf () in
        trans := (i, c, f) :: !trans;
        (i, f)
    | Ou (a, b) ->
        let i = neuf () in
        let f = neuf () in
        let ia, fa = aux a in
        let ib, fb = aux b in
        eps := (i, ia) :: (i, ib) :: (fa, f) :: (fb, f) :: !eps;
        (i, f)
    | Suite (a, b) ->
        let ia, fa = aux a in
        let ib, fb = aux b in
        eps := (fa, ib) :: !eps;
        (ia, fb)
    | Etoile a ->
        let i = neuf () in
        let f = neuf () in
        let ia, fa = aux a in
        eps := (i, ia) :: (i, f) :: (fa, ia) :: (fa, f) :: !eps;
        (i, f)
  in
  let debut, fin = aux e in
  { nb = !n; trans = !trans; eps = !eps; debut; fin }

(* Les ensembles d'états sont des listes croissantes sans répétition : la
   construction des sous-ensembles compare beaucoup d'ensembles, et il
   faut que deux ensembles égaux s'écrivent pareil. *)
let rec insere x l =
  match l with
  | [] -> [ x ]
  | t :: q -> if x = t then l else if x < t then x :: l else t :: insere x q

let reunion a b = List.fold_left (fun acc x -> insere x acc) a b

(* La fermeture spontanée : tout ce qu'on atteint sans lire de lettre. *)
let fermeture a ensemble =
  let vu = ref ensemble and pile = ref ensemble in
  while !pile <> [] do
    match !pile with
    | [] -> ()
    | s :: reste ->
        pile := reste;
        List.iter
          (fun (x, y) ->
            if x = s && not (List.mem y !vu) then begin
              vu := insere y !vu;
              pile := y :: !pile
            end)
          a.eps
  done;
  !vu

let avance a ensemble c =
  fermeture a
    (List.fold_left
       (fun acc (x, d, y) -> if d = c && List.mem x ensemble then insere y acc else acc)
       [] a.trans)

let alphabet a =
  List.fold_left (fun acc (_, c, _) -> if List.mem c acc then acc else c :: acc) [] a.trans

(* La construction des sous-ensembles : un état du déterminisé est un
   ensemble d'états du non déterministe.  Il peut y en avoir 2^n, mais en
   pratique on n'en construit qu'une poignée. *)
type afd = { etats : int list list; regles : (int list * char * int list) list }

let determinise a =
  let lettres = List.sort compare (alphabet a) in
  let depart = fermeture a [ a.debut ] in
  let etats = ref [ depart ] and regles = ref [] and a_traiter = ref [ depart ] in
  while !a_traiter <> [] do
    match !a_traiter with
    | [] -> ()
    | e :: reste ->
        a_traiter := reste;
        List.iter
          (fun c ->
            let suivant = avance a e c in
            if suivant <> [] then begin
              regles := (e, c, suivant) :: !regles;
              if not (List.mem suivant !etats) then begin
                etats := suivant :: !etats;
                a_traiter := suivant :: !a_traiter
              end
            end)
          lettres
  done;
  { etats = !etats; regles = !regles }

let reconnait a d mot =
  let courant = ref (fermeture a [ a.debut ]) and vivant = ref true in
  for i = 0 to String.length mot - 1 do
    if !vivant then begin
      let suite =
        List.fold_left
          (fun acc (e, c, s) -> if e = !courant && c = mot.[i] then s else acc)
          [] d.regles
      in
      if suite = [] then vivant := false else courant := suite
    end
  done;
  !vivant && List.mem a.fin !courant

let () =
  (* (a|b)* a b : les mots sur {a, b} qui finissent par « ab ». *)
  let e =
    Suite (Etoile (Ou (Car 'a', Car 'b')), Suite (Car 'a', Car 'b'))
  in
  let a = construit e in
  print_int a.nb;
  print_char ' ';
  print_int (List.length a.trans);
  print_char ' ';
  print_int (List.length a.eps);
  print_newline ();
  let d = determinise a in
  print_int (List.length d.etats);
  print_char ' ';
  print_int (List.length d.regles);
  print_newline ();
  List.iter
    (fun mot ->
      print_string mot;
      print_char ':';
      print_string (if reconnait a d mot then "oui " else "non "))
    [ "ab"; "aab"; "bbab"; "ba"; "abb"; "" ];
  print_newline ()
