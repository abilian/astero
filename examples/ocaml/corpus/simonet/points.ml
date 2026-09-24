(* Les deux points les plus proches.  D'après le TP 2 de Vincent Simonet
   (MPSI, 2001) : la méthode naïve en O(n^2), puis un tri, puis « diviser
   pour régner » en O(n log n).

   Les coordonnées sont entières et on compare des carrés de distances :
   la racine ne changerait pas l'ordre et ferait entrer les flottants. *)

type point = { px : int; py : int }

(* Le carré d'un écart, pour comparer sans jamais extraire de racine. *)
let ecart2 a b =
  let e = a - b in
  e * e

let distance2 a b =
  ecart2 a.px b.px + ecart2 a.py b.py

(* Méthode naïve : tous les couples de l'intervalle [i, j[. *)
let naif_intervalle t i j =
  let meilleur = ref (distance2 t.(i) t.(i + 1)) in
  for k = i to j - 1 do
    for l = k + 1 to j - 1 do
      meilleur := min !meilleur (distance2 t.(k) t.(l))
    done
  done;
  !meilleur

let naif t = naif_intervalle t 0 (Array.length t)

let trie_par_abscisse t =
  let u = Array.copy t in
  Array.sort (fun a b -> compare a.px b.px) u;
  u

(* Diviser pour régner, sur un tableau déjà trié par abscisse.  Les deux
   moitiés donnent une distance d ; il reste à regarder la bande verticale
   de largeur 2d autour de la coupure, où un couple peut être à cheval. *)
let rec proches t i j =
  if j - i <= 3 then naif_intervalle t i j
  else begin
    let m = (i + j) / 2 in
    let xm = t.(m).px in
    let d = ref (min (proches t i m) (proches t m j)) in
    let bande = ref [] in
    for k = i to j - 1 do
      if ecart2 t.(k).px xm < !d then bande := t.(k) :: !bande
    done;
    let b = Array.of_list (List.sort (fun a c -> compare a.py c.py) !bande) in
    let n = Array.length b in
    for k = 0 to n - 1 do
      let l = ref (k + 1) in
      while !l < n && ecart2 b.(!l).py b.(k).py < !d do
        d := min !d (distance2 b.(k) b.(!l));
        incr l
      done
    done;
    !d
  end

let plus_proches t = proches (trie_par_abscisse t) 0 (Array.length t)

let () =
  let t =
    [|
      { px = 0; py = 0 };
      { px = 12; py = 30 };
      { px = 40; py = 50 };
      { px = 5; py = 1 };
      { px = 12; py = 10 };
      { px = 3; py = 4 };
      { px = 41; py = 52 };
      { px = 20; py = 21 };
    |]
  in
  print_int (naif t);
  print_char ' ';
  print_int (plus_proches t);
  print_newline ();
  let u = trie_par_abscisse t in
  Array.iter
    (fun p ->
      print_int p.px;
      print_char ' ')
    u;
  print_newline ()
