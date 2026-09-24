(* Récursivité : Hanoï, parties d'un ensemble, permutations, code de Gray. *)

let rec hanoi n depart arrivee intermediaire =
  if n > 0 then begin
    hanoi (n - 1) depart intermediaire arrivee;
    print_string depart;
    print_string arrivee;
    print_char ' ';
    hanoi (n - 1) intermediaire arrivee depart
  end

let rec coups n = if n = 0 then 0 else (2 * coups (n - 1)) + 1

let rec parties l =
  match l with
  | [] -> [ [] ]
  | t :: q ->
      let sans = parties q in
      sans @ List.map (fun s -> t :: s) sans

let rec insertions x l =
  match l with
  | [] -> [ [ x ] ]
  | t :: q -> (x :: l) :: List.map (fun p -> t :: p) (insertions x q)

let rec permutations l =
  match l with
  | [] -> [ [] ]
  | t :: q -> List.concat (List.map (insertions t) (permutations q))

let rec gray n =
  if n = 0 then [ [] ]
  else
    let precedent = gray (n - 1) in
    List.map (fun c -> 0 :: c) precedent
    @ List.map (fun c -> 1 :: c) (List.rev precedent)

let rec factorielle n = if n <= 1 then 1 else n * factorielle (n - 1)

let () =
  hanoi 2 "A" "C" "B";
  print_newline ();
  print_int (coups 5);
  print_char ' ';
  print_int (List.length (parties [ 1; 2; 3 ]));
  print_char ' ';
  print_int (List.length (permutations [ 1; 2; 3 ]));
  print_char ' ';
  print_int (factorielle 5);
  print_newline ();
  List.iter
    (fun c ->
      List.iter print_int c;
      print_char ' ')
    (gray 3)
