(* Recherche de motifs.  D'après le TP 7 de Vincent Simonet (MP, 2003) :
   trouver toutes les occurrences d'un motif dans un texte.

   La méthode naïve compare le motif à chaque position.  Knuth, Morris et
   Pratt évitent de reculer dans le texte en calculant d'avance, pour
   chaque préfixe du motif, la longueur de son plus long bord.  Boyer et
   Moore comparent de droite à gauche, ce qui permet de sauter plusieurs
   positions d'un coup. *)

let naif motif texte =
  let m = String.length motif and n = String.length texte in
  let trouve = ref [] in
  for i = n - m downto 0 do
    let egal = ref true in
    for j = 0 to m - 1 do
      if texte.[i + j] <> motif.[j] then egal := false
    done;
    if !egal then trouve := i :: !trouve
  done;
  !trouve

(* Un bord d'un mot est un préfixe qui en est aussi un suffixe, propre.
   bords.(j) est la longueur du plus long bord des j premières lettres du
   motif : c'est de là que l'on repart après un échec. *)
let bords motif =
  let m = String.length motif in
  let b = Array.make (m + 1) 0 in
  let k = ref 0 in
  for j = 1 to m - 1 do
    while !k > 0 && motif.[!k] <> motif.[j] do
      k := b.(!k)
    done;
    if motif.[!k] = motif.[j] then incr k;
    b.(j + 1) <- !k
  done;
  b

let kmp motif texte =
  let m = String.length motif and n = String.length texte in
  let b = bords motif in
  let trouve = ref [] and k = ref 0 in
  for i = 0 to n - 1 do
    while !k > 0 && motif.[!k] <> texte.[i] do
      k := b.(!k)
    done;
    if motif.[!k] = texte.[i] then incr k;
    if !k = m then begin
      trouve := (i - m + 1) :: !trouve;
      k := b.(m)
    end
  done;
  List.rev !trouve

(* L'heuristique du mauvais caractère : pour chaque lettre, de combien on
   peut décaler le motif quand la comparaison échoue sur elle.  Une lettre
   absente du motif permet de sauter sa longueur entière. *)
let mauvais_caractere motif =
  let m = String.length motif in
  let d = Array.make 256 m in
  for j = 0 to m - 2 do
    d.(Char.code motif.[j]) <- m - 1 - j
  done;
  d

let boyer_moore motif texte =
  let m = String.length motif and n = String.length texte in
  let d = mauvais_caractere motif in
  let trouve = ref [] and i = ref 0 in
  while !i <= n - m do
    let j = ref (m - 1) in
    while !j >= 0 && motif.[!j] = texte.[!i + !j] do
      decr j
    done;
    if !j < 0 then trouve := !i :: !trouve;
    i := !i + d.(Char.code texte.[!i + m - 1])
  done;
  List.rev !trouve

let affiche l =
  List.iter
    (fun i ->
      print_int i;
      print_char ' ')
    l;
  print_newline ()

let () =
  let texte = "abracadabra abracadabra" and motif = "abra" in
  affiche (naif motif texte);
  affiche (kmp motif texte);
  affiche (boyer_moore motif texte);
  Array.iter
    (fun k ->
      print_int k;
      print_char ' ')
    (bords "ababaca");
  print_newline ();
  (* Le cas où la méthode naïve travaille le plus : un texte et un motif
     qui se ressemblent partout. *)
  let t = "aaaaaaaaaa" and m = "aaa" in
  affiche (naif m t);
  affiche (kmp m t);
  affiche (boyer_moore m t);
  print_string (if naif m t = kmp m t && kmp m t = boyer_moore m t then "accord"
                else "desaccord");
  print_newline ()
