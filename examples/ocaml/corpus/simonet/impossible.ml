(* Le problème impossible.  D'après le TP 10 de Vincent Simonet (MPSI,
   2002), énigme posée par Martin Gardner.

   Un mathématicien choisit x et y avec 2 <= x <= y <= 100.  Il donne la
   somme à M1 et le produit à M2, et chacun sait ce que l'autre a reçu.
   M1 dit « tu ne peux pas trouver », M2 répond « maintenant je peux », et
   M1 conclut « alors moi aussi ».  Ces trois phrases suffisent.

   Le crible d'Ératosthène sert à voir pourquoi la première phrase est
   informative : si la somme était celle de deux nombres premiers, M2
   aurait pu trouver du premier coup. *)

let n = 100

let eratosthene m =
  let t = Array.make m true in
  t.(0) <- false;
  t.(1) <- false;
  for i = 2 to m - 1 do
    if t.(i) then begin
      let j = ref (2 * i) in
      while !j < m do
        t.(!j) <- false;
        j := !j + i
      done
    end
  done;
  t

let decompose_somme t s =
  let oui = ref false in
  for x = 2 to s / 2 do
    if x < Array.length t && s - x < Array.length t && t.(x) && t.(s - x) then
      oui := true
  done;
  !oui

(* Les sommes que la première phrase de M1 laisse encore possibles, dans
   cette première analyse : celles qui ne sont pas somme de deux premiers. *)
let sommes m =
  let t = eratosthene ((2 * m) + 1) in
  let l = ref [] in
  for s = 2 * m downto 4 do
    if not (decompose_somme t s) then l := s :: !l
  done;
  !l

(* L'analyse complète.  On compte, pour chaque produit, ses factorisations
   dans l'intervalle : c'est ce que M2 voit. *)
let factorisations () =
  let compte = Array.make ((n * n) + 1) 0 in
  for x = 2 to n do
    for y = x to n do
      compte.(x * y) <- compte.(x * y) + 1
    done
  done;
  compte

(* Phrase 1 : « tu ne peux pas trouver ».  Aucune décomposition de la
   somme ne doit donner un produit qui se factorise d'une seule façon. *)
let sommes_sures compte =
  let sur = Array.make ((2 * n) + 1) true in
  for x = 2 to n do
    for y = x to n do
      if compte.(x * y) < 2 then sur.(x + y) <- false
    done
  done;
  sur

(* Phrase 2 : « maintenant je peux ».  Parmi les factorisations du
   produit, une seule a une somme que la phrase 1 laisse possible. *)
let produits_surs sur =
  let compte = Array.make ((n * n) + 1) 0 in
  for x = 2 to n do
    for y = x to n do
      if sur.(x + y) then compte.(x * y) <- compte.(x * y) + 1
    done
  done;
  compte

(* Phrase 3 : « alors moi aussi ».  Parmi les décompositions de la somme,
   une seule survit à la phrase 2. *)
let resout () =
  let sur = sommes_sures (factorisations ()) in
  let apres = produits_surs sur in
  let solution = ref (0, 0) and combien = Array.make ((2 * n) + 1) 0 in
  for x = 2 to n do
    for y = x to n do
      if sur.(x + y) && apres.(x * y) = 1 then
        combien.(x + y) <- combien.(x + y) + 1
    done
  done;
  for x = 2 to n do
    for y = x to n do
      if sur.(x + y) && apres.(x * y) = 1 && combien.(x + y) = 1 then
        solution := (x, y)
    done
  done;
  !solution

let () =
  let t = eratosthene 30 in
  for i = 2 to 29 do
    if t.(i) then begin
      print_int i;
      print_char ' '
    end
  done;
  print_newline ();
  print_string (if decompose_somme t 24 then "oui " else "non ");
  print_string (if decompose_somme t 23 then "oui" else "non");
  print_newline ();
  (* Les premières sommes que la phrase 1 laisse possibles, si x et y sont
     dans [2, 10]. *)
  List.iter
    (fun s ->
      print_int s;
      print_char ' ')
    (sommes 10);
  print_newline ();
  let x, y = resout () in
  print_int x;
  print_char ' ';
  print_int y;
  print_char ' ';
  print_int (x + y);
  print_char ' ';
  print_int (x * y);
  print_newline ()
