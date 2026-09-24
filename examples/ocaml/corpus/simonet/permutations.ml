(* Permutations.  D'après le TP 5 de Vincent Simonet (MPSI, 2001) : une
   permutation de {0, ..., n-1} est un tableau s tel que s.(i) est l'image
   de i.  On les compose, on les énumère dans l'ordre lexicographique, et
   on les décompose en cycles. *)

let identite n = Array.init n (fun i -> i)

(* Un tableau est une permutation si chaque valeur de 0 à n-1 y figure une
   fois et une seule. *)
let est_permutation s =
  let n = Array.length s in
  let vu = Array.make n false in
  let bon = ref true in
  for i = 0 to n - 1 do
    if s.(i) < 0 || s.(i) >= n then bon := false
    else if vu.(s.(i)) then bon := false
    else vu.(s.(i)) <- true
  done;
  !bon

(* (s o t).(i) = s.(t.(i)) : on applique t, puis s. *)
let compose s t = Array.init (Array.length t) (fun i -> s.(t.(i)))

let inverse s =
  let n = Array.length s in
  let r = Array.make n 0 in
  for i = 0 to n - 1 do
    r.(s.(i)) <- i
  done;
  r

(* Successeur dans l'ordre lexicographique, ou le tableau vide s'il n'y en
   a pas.  On cherche depuis la fin le dernier endroit qui monte, on y met
   la plus petite valeur encore plus grande, et on retourne la queue. *)
let suivante s =
  let n = Array.length s in
  let r = Array.copy s in
  let i = ref (n - 2) in
  while !i >= 0 && r.(!i) >= r.(!i + 1) do
    decr i
  done;
  if !i < 0 then [||]
  else begin
    let j = ref (n - 1) in
    while r.(!j) <= r.(!i) do
      decr j
    done;
    let echange a b =
      let v = r.(a) in
      r.(a) <- r.(b);
      r.(b) <- v
    in
    echange !i !j;
    let g = ref (!i + 1) and d = ref (n - 1) in
    while !g < !d do
      echange !g !d;
      incr g;
      decr d
    done;
    r
  end

let rec enumere s =
  if Array.length s = 0 then [] else s :: enumere (suivante s)

let affiche s =
  Array.iter
    (fun v ->
      print_int v;
      print_char ' ')
    s;
  print_newline ()

(* Décomposition en cycles : on part de chaque point non encore visité et
   on suit les images jusqu'à revenir au départ. *)
let cycles s =
  let n = Array.length s in
  let vu = Array.make n false in
  let sortie = ref [] in
  for depart = n - 1 downto 0 do
    if not vu.(depart) then begin
      let c = ref [] and i = ref depart in
      while not vu.(!i) do
        vu.(!i) <- true;
        c := !i :: !c;
        i := s.(!i)
      done;
      sortie := List.rev !c :: !sortie
    end
  done;
  !sortie

(* La signature vaut (-1) élevé au nombre de transpositions, soit un
   changement de signe par cycle de longueur paire. *)
let signature s =
  List.fold_left
    (fun acc c -> if List.length c mod 2 = 0 then -acc else acc)
    1 (cycles s)

let rec pgcd a b = if b = 0 then a else pgcd b (a mod b)
let ppcm a b = a / pgcd a b * b

(* L'ordre est le plus petit k tel que s^k soit l'identité : le ppcm des
   longueurs des cycles. *)
let ordre s = List.fold_left (fun acc c -> ppcm acc (List.length c)) 1 (cycles s)

let affiche_cycles s =
  List.iter
    (fun c ->
      print_char '(';
      List.iter
        (fun v ->
          print_int v;
          print_char ' ')
        c;
      print_string ") ")
    (cycles s);
  print_newline ()

let () =
  let s = [| 2; 0; 1; 4; 3 |] in
  print_string (if est_permutation s then "oui" else "non");
  print_char ' ';
  print_string (if est_permutation [| 0; 0; 1 |] then "oui" else "non");
  print_newline ();
  affiche (compose s (inverse s));
  affiche (compose s s);
  affiche_cycles s;
  print_int (signature s);
  print_char ' ';
  print_int (ordre s);
  print_newline ();
  List.iter affiche (enumere (identite 3))
