(* Compression LZW.  D'après le TP 7 de Vincent Simonet (MPSI, 2001) : un
   dictionnaire que compresseur et décompresseur construisent chacun de
   leur côté, sans jamais se le transmettre.

   Le dictionnaire part des 256 caractères ; chaque fois qu'un motif ne
   s'y trouve pas, on émet le code du plus long préfixe connu et on
   ajoute le motif.  Le décompresseur refait les mêmes ajouts. *)

type dictionnaire = { mutable taille : int; mots : string array }

let initial capacite =
  let mots = Array.make capacite "" in
  for i = 0 to 255 do
    mots.(i) <- String.make 1 (Char.chr i)
  done;
  { taille = 256; mots }

let ajoute d mot =
  if d.taille < Array.length d.mots then begin
    d.mots.(d.taille) <- mot;
    d.taille <- d.taille + 1
  end

(* Le dictionnaire est un tableau, donc la recherche est linéaire : c'est
   le point que l'on améliore avec une table de hachage. *)
let code d mot =
  let trouve = ref (-1) in
  for i = d.taille - 1 downto 0 do
    if d.mots.(i) = mot then trouve := i
  done;
  if !trouve < 0 then raise Not_found;
  !trouve

let connu d mot = try ignore (code d mot); true with Not_found -> false

let comprime texte =
  let d = initial 512 in
  let sortie = ref [] and courant = ref "" in
  for i = 0 to String.length texte - 1 do
    let c = String.make 1 texte.[i] in
    if connu d (!courant ^ c) then courant := !courant ^ c
    else begin
      sortie := code d !courant :: !sortie;
      ajoute d (!courant ^ c);
      courant := c
    end
  done;
  if !courant <> "" then sortie := code d !courant :: !sortie;
  List.rev !sortie

(* Le décompresseur a un temps de retard : il n'ajoute une entrée qu'une
   fois le motif suivant connu.  Le cas où un code désigne l'entrée en
   train d'être créée est le seul point délicat. *)
let decomprime codes =
  match codes with
  | [] -> ""
  | premier :: reste ->
      let d = initial 512 in
      let precedent = ref d.mots.(premier) in
      let sortie = ref [ !precedent ] in
      List.iter
        (fun k ->
          let mot =
            if k < d.taille then d.mots.(k)
            else !precedent ^ String.make 1 (!precedent).[0]
          in
          sortie := mot :: !sortie;
          ajoute d (!precedent ^ String.make 1 mot.[0]);
          precedent := mot)
        reste;
      String.concat "" (List.rev !sortie)

(* Le taux de compression, en pour cent : chaque code tient sur 9 bits,
   chaque caractère du texte sur 8. *)
let taux texte codes =
  9 * List.length codes * 100 / (8 * String.length texte)

let () =
  let texte = "TOBEORNOTTOBEORTOBEORNOT" in
  let codes = comprime texte in
  List.iter
    (fun k ->
      print_int k;
      print_char ' ')
    codes;
  print_newline ();
  print_int (List.length codes);
  print_char ' ';
  print_int (String.length texte);
  print_char ' ';
  print_int (taux texte codes);
  print_newline ();
  let rendu = decomprime codes in
  print_string rendu;
  print_char ' ';
  print_string (if rendu = texte then "identique" else "different");
  print_newline ();
  (* Le cas délicat : un motif dont le code est émis avant que le
     décompresseur ne l'ait construit. *)
  let piege = "AAAAAA" in
  let c = comprime piege in
  List.iter
    (fun k ->
      print_int k;
      print_char ' ')
    c;
  print_string (if decomprime c = piege then "identique" else "different");
  print_newline ()
