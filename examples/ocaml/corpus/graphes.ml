(* Graphes en listes d'adjacence : parcours en profondeur et en largeur. *)

let voisins g s = g.(s)
let ordre g = Array.length g

let degres g =
  let d = Array.make (ordre g) 0 in
  for s = 0 to ordre g - 1 do
    d.(s) <- List.length g.(s)
  done;
  d

let profondeur g depart =
  let vus = Array.make (ordre g) false in
  let visite_ordre = ref [] in
  let rec visite s =
    if not vus.(s) then begin
      vus.(s) <- true;
      visite_ordre := s :: !visite_ordre;
      List.iter visite (voisins g s)
    end
  in
  visite depart;
  List.rev !visite_ordre

let largeur g depart =
  let vus = Array.make (ordre g) false in
  let visite_ordre = ref [] in
  let file = ref [ depart ] in
  vus.(depart) <- true;
  while !file <> [] do
    match !file with
    | [] -> ()
    | s :: reste ->
        file := reste;
        visite_ordre := s :: !visite_ordre;
        List.iter
          (fun v ->
            if not vus.(v) then begin
              vus.(v) <- true;
              file := !file @ [ v ]
            end)
          (voisins g s)
  done;
  List.rev !visite_ordre

let connexe g = List.length (profondeur g 0) = ordre g

let () =
  let g = [| [ 1; 2 ]; [ 0; 3 ]; [ 0 ]; [ 1 ] |] in
  List.iter print_int (profondeur g 0);
  print_char ' ';
  List.iter print_int (largeur g 0);
  print_newline ();
  Array.iter print_int (degres g);
  print_char ' ';
  print_string (if connexe g then "connexe" else "non connexe")
