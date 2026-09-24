(* Les tris du programme : insertion, sélection, fusion, pivot. *)

let rec insere x l =
  match l with
  | [] -> [ x ]
  | t :: q -> if x <= t then x :: l else t :: insere x q

let rec tri_insertion l =
  match l with
  | [] -> []
  | t :: q -> insere t (tri_insertion q)

let rec extrait_min l =
  match l with
  | [] -> failwith "extrait_min : liste vide"
  | [ x ] -> (x, [])
  | t :: q ->
      let m, reste = extrait_min q in
      if t <= m then (t, q) else (m, t :: reste)

let rec tri_selection l =
  match l with
  | [] -> []
  | _ ->
      let m, reste = extrait_min l in
      m :: tri_selection reste

let rec scinde l =
  match l with
  | [] -> ([], [])
  | [ x ] -> ([ x ], [])
  | a :: b :: q ->
      let g, d = scinde q in
      (a :: g, b :: d)

let rec fusionne a b =
  match (a, b) with
  | [], l | l, [] -> l
  | x :: xs, y :: ys -> if x <= y then x :: fusionne xs b else y :: fusionne a ys

let rec tri_fusion l =
  match l with
  | [] | [ _ ] -> l
  | _ ->
      let g, d = scinde l in
      fusionne (tri_fusion g) (tri_fusion d)

let rec tri_rapide l =
  match l with
  | [] -> []
  | pivot :: reste ->
      let petits = List.filter (fun x -> x <= pivot) reste in
      let grands = List.filter (fun x -> x > pivot) reste in
      tri_rapide petits @ (pivot :: tri_rapide grands)

let rec est_croissante l =
  match l with
  | [] | [ _ ] -> true
  | a :: (b :: _ as reste) -> a <= b && est_croissante reste

let affiche l =
  List.iter
    (fun x ->
      print_int x;
      print_char ' ')
    l

let () =
  let l = [ 5; 3; 8; 1; 9; 2 ] in
  affiche (tri_insertion l);
  print_newline ();
  affiche (tri_selection l);
  print_newline ();
  affiche (tri_fusion l);
  print_newline ();
  affiche (tri_rapide l);
  print_newline ();
  print_string (if est_croissante (tri_fusion l) then "triee" else "non triee")
