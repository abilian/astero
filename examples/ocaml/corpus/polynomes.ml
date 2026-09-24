(* Polynômes en représentation dense : un tableau de coefficients, le
   coefficient d'indice i devant X^i. *)

let degre p =
  let d = ref (-1) in
  for i = 0 to Array.length p - 1 do
    if p.(i) <> 0 then d := i
  done;
  !d

let evalue p x =
  (* Horner, de droite à gauche. *)
  let v = ref 0 in
  for i = Array.length p - 1 downto 0 do
    v := (!v * x) + p.(i)
  done;
  !v

let somme p q =
  let n = max (Array.length p) (Array.length q) in
  let r = Array.make n 0 in
  for i = 0 to Array.length p - 1 do
    r.(i) <- r.(i) + p.(i)
  done;
  for i = 0 to Array.length q - 1 do
    r.(i) <- r.(i) + q.(i)
  done;
  r

let produit p q =
  let n = Array.length p and m = Array.length q in
  let r = Array.make (n + m - 1) 0 in
  for i = 0 to n - 1 do
    for j = 0 to m - 1 do
      r.(i + j) <- r.(i + j) + (p.(i) * q.(j))
    done
  done;
  r

let derive p =
  let n = Array.length p in
  if n <= 1 then [| 0 |]
  else begin
    let r = Array.make (n - 1) 0 in
    for i = 1 to n - 1 do
      r.(i - 1) <- i * p.(i)
    done;
    r
  end

let affiche p =
  Array.iter
    (fun c ->
      print_int c;
      print_char ' ')
    p

let () =
  let p = [| 1; 0; 2 |] and q = [| 0; 3 |] in
  affiche (somme p q);
  print_newline ();
  affiche (produit p q);
  print_newline ();
  affiche (derive p);
  print_newline ();
  print_int (evalue p 2);
  print_char ' ';
  print_int (degre p)
