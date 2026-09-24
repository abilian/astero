(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Probleme_Sac_a_dos
   at commit 6e39653f9df8:
   solutions/Grimaud_UnboundedKnapsack_dp.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

type knapsack = {
  w : int;
  n : int;
  values : int array;
  weights : int array
}

type solution = float array

let print_knapsack (ks : knapsack) : unit =
  Printf.printf "Knapsack of weight %d\n" ks.w;
  Printf.printf "  with %d objects :" ks.n;
  for i = 0 to ks.n - 1 do
    Printf.printf " (%d, %d)" ks.values.(i) ks.weights.(i)
  done;
  Printf.printf "\n"

let print_solution (ks : knapsack) (sol : float array) : unit =
  (* Compute total weight used and total value *)
  let total_value, total_weight =
    Array.fold_left (fun (v, w) i ->
      (v +. sol.(i) *. float_of_int ks.values.(i),
       w +. sol.(i) *. float_of_int ks.weights.(i))
    ) (0.0, 0.0) (Array.init ks.n (fun i -> i))
  in
  Printf.printf "Knapsack of weight %d, total weight %.1f, total value %.1f\n" ks.w total_weight total_value;
  Printf.printf "  with :";
  for i = 0 to ks.n - 1 do
    Printf.printf " %.1f*(%d, %d)" sol.(i) ks.values.(i) ks.weights.(i)
  done;
  Printf.printf "\n"

let sort_knapsack (ks : knapsack) : knapsack =
  (* Create an array of indices *)
  let indices = Array.init ks.n (fun i -> i) in
  (* Sort based on decreasing value/weight ratio, without using floats *)
  Array.sort (fun i j ->
    let vi = ks.values.(i) in
    let wi = ks.weights.(i) in
    let vj = ks.values.(j) in
    let wj = ks.weights.(j) in
    compare (vj * wi) (vi * wj)
  ) indices;
  (* Rebuild new values and weights arrays *)
  let new_values = Array.init ks.n (fun i -> ks.values.(indices.(i))) in
  let new_weights = Array.init ks.n (fun i -> ks.weights.(indices.(i))) in
  (* Return a new knapsack instance *)
  {
    w = ks.w;
    n = ks.n;
    values = new_values;
    weights = new_weights;
  }

let verify_knapsack (ks : knapsack) (sol : solution) : float option =
  let total_value, total_weight =
    Array.fold_left (fun (v, w) i ->
      (v +. sol.(i) *. float_of_int ks.values.(i),
       w +. sol.(i) *. float_of_int ks.weights.(i))
    ) (0.0, 0.0) (Array.init ks.n (fun i -> i))
  in
  if total_weight <= float_of_int ks.w then
    Some total_value
  else
    None

let unboundedknapsack_dp_value (ks : knapsack) : int =
  let dp = Array.make (ks.w + 1) 0 in
  for j = 0 to ks.w do
    for i = 0 to ks.n - 1 do
      if ks.weights.(i) <= j then
        let candidate = dp.(j - ks.weights.(i)) + ks.values.(i) in
        if candidate > dp.(j) then
          dp.(j) <- candidate
    done
  done;
  dp.(ks.w)

let unboundedknapsack_dp (ks : knapsack) : solution =
  (* Compute v max *)
  let dp = Array.make (ks.w + 1) 0 in
  for j = 0 to ks.w do
    for i = 0 to ks.n - 1 do
      if ks.weights.(i) <= j then
        let candidate = dp.(j - ks.weights.(i)) + ks.values.(i) in
        if candidate > dp.(j) then
          dp.(j) <- candidate
    done
  done;

  (* lambda *)
  let lambda = Array.make ks.n 0.0 in
  let rec reconstruct j =
    if j > 0 then
      let rec find i =
        if i<ks.n && ks.weights.(i) <= j &&
           dp.(j) = dp.(j - ks.weights.(i)) + ks.values.(i) then
          begin
            lambda.(i) <- lambda.(i) +. 1.;
            reconstruct (j - ks.weights.(i))
          end
        else
          find (i + 1)
      in
      find 0
  in
  reconstruct ks.w;
  lambda

let () =
  let ks = {
    w = 35;
    n = 5;
    values = [| 27; 50; 51; 142; 39 |];
    weights = [| 3; 9; 30; 32; 5 |];
  } in
  print_knapsack ks;
  let sorted_ks = sort_knapsack ks in
  print_knapsack sorted_ks;
  let sol_v = unboundedknapsack_dp_value sorted_ks in
  Printf.printf "Found value : %d\n" sol_v;
  let sol = unboundedknapsack_dp sorted_ks in
  print_solution sorted_ks sol
  
