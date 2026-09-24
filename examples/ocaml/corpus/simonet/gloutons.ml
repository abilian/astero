(* Algorithmes gloutons.  D'après le TP 4 de Vincent Simonet (MPSI, 2001 et
   2002) : cinq problèmes d'optimisation où l'on prend à chaque étape ce
   qui semble le meilleur sur le moment.  Deux d'entre eux montrent qu'un
   glouton peut se tromper. *)

(* Le voleur intelligent.  Des matières fractionnables : la i-ème vaut
   prix.(i) par kilo et il y en a quantite.(i) kilos, les prix étant
   rangés dans l'ordre croissant.  Le voleur porte au plus charge kilos.
   On commence par la plus chère, dont on prend tout ce qu'on peut. *)
let voleur quantite charge =
  let n = Array.length quantite in
  let reste = ref charge in
  let butin = Array.make n 0 in
  for i = n - 1 downto 0 do
    butin.(i) <- min quantite.(i) !reste;
    reste := !reste - butin.(i)
  done;
  butin

(* Réservation SNCF.  La personne i veut le train voulu.(i) ; il y a k
   trains, chacun de capacité c.  Tout le monde peut-il partir comme il
   l'entend ? *)
let possible c voulu k =
  let trains = Array.make k 0 in
  let convient = ref true in
  for i = 0 to Array.length voulu - 1 do
    let t = voulu.(i) in
    trains.(t) <- trains.(t) + 1;
    if trains.(t) > c then convient := false
  done;
  !convient

exception Complet

(* Si son train est plein, la personne accepte un train ultérieur.  On
   affecte chacun au premier train libre à partir de celui qu'elle veut. *)
let sncf c voulu k =
  let n = Array.length voulu in
  let trains = Array.make k 0 in
  let place = Array.make n 0 in
  for i = 0 to n - 1 do
    let j = ref voulu.(i) in
    while !j < k && trains.(!j) >= c do
      incr j
    done;
    if !j = k then raise Complet;
    place.(i) <- !j;
    trains.(!j) <- trains.(!j) + 1
  done;
  place

(* Remplissage d'un camion.  On cherche le plus grand poids inférieur ou
   égal à la charge que l'on puisse former en sommant des marchandises.
   On construit à chaque étape la liste des poids atteignables. *)
let rec ajoute a l = match l with [] -> [] | t :: q -> (t + a) :: ajoute a q

let rec retire x l =
  match l with
  | [] -> []
  | t :: q when t > x -> retire x q
  | t :: q -> t :: retire x q

let rec maximum l =
  match l with
  | [] -> failwith "liste vide"
  | [ t ] -> t
  | t :: q -> max t (maximum q)

let camion poids charge =
  let atteignables = ref [ 0 ] in
  for i = 0 to Array.length poids - 1 do
    atteignables := retire charge (ajoute poids.(i) !atteignables) @ !atteignables
  done;
  maximum !atteignables

(* Réservation d'une salle.  L'événement i occupe [debut.(i), fin.(i)[, et
   les événements sont rangés par heure de fin croissante.  On prend à
   chaque fois celui qui finit le plus tôt parmi ceux encore possibles. *)
let salle debut fin =
  let n = Array.length fin in
  let rec choisit libre i =
    if i >= n then []
    else if debut.(i) < libre then choisit libre (i + 1)
    else i :: choisit fin.(i) (i + 1)
  in
  choisit 0 0

(* L'angoisse de la panne sèche.  d.(i) est la distance de la station i-1 à
   la station i, et le réservoir plein parcourt reservoir.  Pour s'arrêter
   le moins souvent, on va toujours aussi loin que possible. *)
let rapide d reservoir =
  let n = Array.length d in
  let rec avance i essence =
    if i = n then []
    else if d.(i) > essence then i :: avance (i + 1) (reservoir - d.(i))
    else avance (i + 1) (essence - d.(i))
  in
  avance 0 reservoir

let affiche_tableau t =
  Array.iter
    (fun v ->
      print_int v;
      print_char ' ')
    t;
  print_newline ()

let affiche_liste l =
  List.iter
    (fun v ->
      print_int v;
      print_char ' ')
    l;
  print_newline ()

let () =
  (* Trois matières, à 1, 4 et 9 euros le kilo, 5 kilos de chaque, un sac
     de 8 kilos : on prend les 5 kilos à 9 puis 3 kilos à 4. *)
  affiche_tableau (voleur [| 5; 5; 5 |] 8);
  let voulu = [| 0; 0; 0; 1; 2 |] in
  print_string (if possible 2 voulu 3 then "oui" else "non");
  print_char ' ';
  print_string (if possible 3 voulu 3 then "oui" else "non");
  print_newline ();
  affiche_tableau (sncf 2 voulu 3);
  print_int (camion [| 3; 5; 8; 11 |] 15);
  print_char ' ';
  print_int (camion [| 3; 5; 8; 11 |] 6);
  print_newline ();
  affiche_liste (salle [| 0; 3; 1; 5; 8 |] [| 2; 4; 6; 7; 9 |]);
  affiche_liste (rapide [| 3; 4; 2; 5; 1 |] 6)
