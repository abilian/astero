(* Allocation mémoire.  D'après le TP 2 de Vincent Simonet (MP, 2003),
   tiré de Centrale-Supélec 1999.

   La mémoire est un tableau de mots ; un programme demande des blocs
   contigus et les rend.  Il faut savoir où sont les trous.  Deux
   représentations : une liste de blocs libres à côté de la mémoire, puis
   la même liste chaînée à l'intérieur de la mémoire elle-même. *)

exception Plus_de_memoire

(* La liste des blocs libres, en couples (adresse, taille), triée par
   adresse.  Au départ, un seul bloc : toute la mémoire. *)
let memoire_libre n = [ (0, n) ]

(* Premier ajustement : le premier bloc assez grand.  Rapide, mais laisse
   des miettes au début de la liste. *)
let rec alloc_first taille libres =
  match libres with
  | [] -> raise Plus_de_memoire
  | (a, t) :: reste when t > taille -> (a, (a + taille, t - taille) :: reste)
  | (a, t) :: reste when t = taille -> (a, reste)
  | bloc :: reste ->
      let adresse, restants = alloc_first taille reste in
      (adresse, bloc :: restants)

(* Meilleur ajustement : le plus petit bloc qui convienne.  Plus lent, et
   les miettes sont plus petites, ce qui n'est pas toujours un progrès. *)
let rec cherche_meilleur taille libres =
  match libres with
  | [] -> -1
  | (_, t) :: reste ->
      let apres = cherche_meilleur taille reste in
      if t < taille then apres
      else if apres < 0 then t
      else min t apres

let alloc_best taille libres =
  let cible = cherche_meilleur taille libres in
  if cible < 0 then raise Plus_de_memoire;
  let rec decoupe l =
    match l with
    | [] -> raise Plus_de_memoire
    | (a, t) :: reste when t = cible ->
        if t = taille then (a, reste) else (a, (a + taille, t - taille) :: reste)
    | bloc :: reste ->
        let adresse, restants = decoupe reste in
        (adresse, bloc :: restants)
  in
  decoupe libres

(* Libération : on remet le bloc à sa place dans la liste triée, puis on
   le fusionne avec ses voisins s'ils le touchent.  Sans cette fusion, la
   mémoire se fragmente jusqu'à ne plus rien pouvoir allouer. *)
let rec insere_bloc a taille libres =
  match libres with
  | [] -> [ (a, taille) ]
  | (b, t) :: reste ->
      if a < b then (a, taille) :: (b, t) :: reste
      else (b, t) :: insere_bloc a taille reste

let rec fusionne libres =
  match libres with
  | (a, t) :: (b, u) :: reste when a + t = b -> fusionne ((a, t + u) :: reste)
  | bloc :: reste -> bloc :: fusionne reste
  | [] -> []

let libere a taille libres = fusionne (insere_bloc a taille libres)

(* Seconde représentation : la liste chaînée vit dans la mémoire.  Chaque
   bloc libre écrit sa taille dans son premier mot et l'adresse du bloc
   suivant dans le second, ce qui ne coûte pas un octet de plus. *)
let vide = -1

let initialise m =
  let n = Array.length m in
  m.(0) <- n;
  m.(1) <- vide;
  0

let rec alloc_chainee m tete taille precedent =
  if tete = vide then raise Plus_de_memoire
  else if m.(tete) >= taille + 2 then begin
    (* On coupe la fin du bloc, ce qui laisse la chaîne intacte. *)
    let adresse = tete + m.(tete) - taille in
    m.(tete) <- m.(tete) - taille;
    adresse
  end
  else alloc_chainee m m.(tete + 1) taille tete

let rec libres_chainees m tete =
  if tete = vide then [] else (tete, m.(tete)) :: libres_chainees m m.(tete + 1)

let affiche libres =
  List.iter
    (fun (a, t) ->
      print_char '(';
      print_int a;
      print_char ',';
      print_int t;
      print_char ')')
    libres;
  print_newline ()

let () =
  let libres = memoire_libre 64 in
  let a, libres = alloc_first 10 libres in
  let b, libres = alloc_first 20 libres in
  print_int a;
  print_char ' ';
  print_int b;
  print_char ' ';
  affiche libres;
  let libres = libere a 10 libres in
  affiche libres;
  (* Premier ajustement contre meilleur ajustement, sur la même liste. *)
  let trous = [ (0, 30); (40, 12); (60, 4) ] in
  let c, apres_first = alloc_first 4 trous in
  let d, apres_best = alloc_best 4 trous in
  print_int c;
  print_char ' ';
  affiche apres_first;
  print_int d;
  print_char ' ';
  affiche apres_best;
  (* La même mémoire, mais la liste est dedans. *)
  let m = Array.make 32 0 in
  let tete = initialise m in
  let x = alloc_chainee m tete 8 vide in
  let y = alloc_chainee m tete 4 vide in
  print_int x;
  print_char ' ';
  print_int y;
  print_char ' ';
  affiche (libres_chainees m tete)
