(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Probleme_Sac_a_dos
   at commit 6e39653f9df8:
   solutions/PriorityQueue.ml
   solutions/Grimaud_01Knapsack_bb.ml
   GPL-3.0, see LICENSE in this directory.
   Changed: the two files are concatenated, with an empty line between, and
   the line `open PriorityQueue` is removed. PriorityQueue.mli is left out. *)

(** {1 PriorityQueue}
    This module provides une simple implementation of a priority queue using a binary heap. *)

(** {2 Types} *)

(** The type representing a priority queue. *)
type 'a priorityqueue = {
  mutable heap : 'a option array;  (** The array representing the heap. *)
  mutable size : int;       (** The current size of the priority queue. *)
  cmp : 'a -> 'a -> bool;   (** The comparison function for priority. *)
}

(** {2 Constants} *)

(** The initial capacity of the priority queue. *)
let initial_capacity = 10

(** {2 Functions} *)

(** [create cmp] creates a new priority queue with a given comparison function [cmp].
    @param cmp The comparison function to determine priority.
    @return A new priority queue.
*)
let create cmp =
  { heap = Array.make initial_capacity None; size = 0; cmp }

(** [size pq] returns the current size of the priority queue [pq].
    @param pq The priority queue.
    @return The current size of the priority queue. *)
let size pq =
  pq.size

(** [is_empty pq] checks if the priority queue [pq] is empty.
    @param pq The priority queue to check.
    @return [true] if the priority queue is empty, [false] otherwise. *)
let is_empty pq =
  pq.size = 0

(** [swap pq i j] swaps the elements at indices [i] and [j] in the priority queue [pq].
    @param pq The priority queue.
    @param i The first index.
    @param j The second index. *)
let swap pq i j =
  let temp = pq.heap.(i) in
  pq.heap.(i) <- pq.heap.(j);
  pq.heap.(j) <- temp

(** [insert pq x] inserts the element [x] into the priority queue [pq].
    @param pq The priority queue.
    @param x The element to insert.
    If the heap is full, the array is resized to accommodate more elements.
    The function maintains the heap property by "bubbling up" the new element as needed.
    @raise Failure if there is an unexpected error during insertion. *)
let insert pq x =
  let rec aux i =
    if i > 0 then
      let parent = (i - 1) / 2 in
      match pq.heap.(i), pq.heap.(parent) with
      | Some i_val, Some p_val ->
        if pq.cmp i_val p_val then (
          swap pq i parent;
          aux parent
        )
      | _ -> failwith "Unexpected priority heap error during insertion..."
  in
  if pq.size = Array.length pq.heap then
    pq.heap <- Array.append pq.heap (Array.make (Array.length pq.heap) None);
  pq.heap.(pq.size) <- Some x;
  aux pq.size;
  pq.size <- pq.size + 1

(** [extract pq] extracts the minimum element from the priority queue [pq].
    @param pq The priority queue.
    @return The minimum element.
    If the heap is not empty, the root element (minimum) is removed, and the last element in the heap is moved to the root.
    The function maintains the heap property by "bubbling down" the new root element as needed.
    @raise Failure if the priority queue is empty or if there is an unexpected error during extraction. *)
let extract pq =
  let rec aux i =
    let left = 2 * i + 1 in
    let right = 2 * i + 2 in
    let smallest = ref i in
    if left < pq.size then (
      match pq.heap.(left), pq.heap.(!smallest) with
      | Some left_val, Some smallest_val -> 
        if pq.cmp left_val smallest_val then
          smallest := left 
      | _ -> failwith "Unexpected priority heap error during extraction..."
    ) ;
    if right < pq.size then (
      match pq.heap.(right), pq.heap.(!smallest) with
      | Some right_val, Some smallest_val -> 
        if pq.cmp right_val smallest_val then
          smallest := right
      | _ -> failwith "Unexpected priority heap error during extraction..." 
    ) ; 
    if !smallest <> i then (
      swap pq i !smallest;
      aux !smallest
    )
  in
  if pq.size = 0 then failwith "PriorityQueue is empty";
  let min = pq.heap.(0) in
  pq.size <- pq.size - 1;
  pq.heap.(0) <- pq.heap.(pq.size);
  pq.heap.(pq.size) <- None;
  aux 0;
  match min with
  | None -> failwith "Unexpected priority heap error during extraction..."
  | Some min -> min




type knapsack = {
  w : int;
  n : int;
  values : int array;
  weights : int array
}

type solution = float array

type node = {
  level  : int;      (* index of the last considered item *)
  value  : int;      (* current total value *)
  weight : int;      (* current total weight *)
  bound  : float;    (* estimated upper bound *)
  sol    : solution; (* partial solution *)
}

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

let print_node (n : node) : unit =
  Printf.printf "Node:\n";
  Printf.printf "  Level: %d - " n.level;
  Printf.printf "  Value: %d - " n.value;
  Printf.printf "  Weight: %d - " n.weight;
  Printf.printf "  Bound: %.2f\n" n.bound;
  Printf.printf "  Solution: [| ";
  Array.iteri (fun i x ->
    if i = Array.length n.sol - 1 then
      Printf.printf "%f" x
    else
      Printf.printf "%f; " x
  ) n.sol;
  Printf.printf " |]\n"

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

(* Relaxation : Compute fractional upper bound from a given node *)
let compute_bound (ks : knapsack) (n : node) : float =
  let weight = ks.w - n.weight in
  let rec fill i weight_left vsup =
    if i >= ks.n || weight_left = 0 then
      vsup
    else
      let vi = ks.values.(i) in
      let wi = ks.weights.(i) in
      if wi <= weight_left then
        fill (i + 1) (weight_left - wi) (vsup +. float_of_int vi)
      else
        vsup +. float_of_int vi *.
                (float_of_int weight_left /. float_of_int wi)
  in
  fill (n.level + 1) weight (float_of_int n.value)   

let binaryknapsack_bb (ks : knapsack) : solution =
  (* Create a priority queue where higher bound means higher priority *)
  let pq = create (fun n1 n2 -> n1.bound > n2.bound) in

  (* Best solution found so far *)
  let best_value = ref 0 in
  let best_solution = ref (Array.make ks.n 0.0) in

  (* Initial root node *)
  let root = {
    level = -1;
    value = 0;
    weight = 0;
    bound = compute_bound ks {
      level = -1; value = 0; weight = 0;
      bound = 0.0; sol = Array.make ks.n 0.0;
    };
    sol = Array.make ks.n 0.0;
  } in
 
  insert pq root;
  
  (* Main loop: explore nodes *)
  while not (is_empty pq) do
    let node = extract pq in
    if node.level < ks.n -1 then
      let next = node.level + 1 in

      (* Try excluding the next item *)
      let sol_excl = Array.copy node.sol in
      sol_excl.(next) <- 0.0;
      let bound_excl = compute_bound ks {
          level = next; value = node.value; weight = node.weight;
          bound = 0.0; sol = sol_excl;
        } in
      if bound_excl > float_of_int !best_value then
        insert pq { level = next; value = node.value; weight = node.weight;
                    bound = bound_excl; sol = sol_excl };
      
      (* Try including the next item *)
      let w_incl = node.weight + ks.weights.(next) in
      if w_incl <= ks.w then (
        let sol_incl = Array.copy node.sol in
        sol_incl.(next) <- 1.0;
        let v_incl = node.value + ks.values.(next) in
        if v_incl > !best_value then (
          best_value := v_incl;
          best_solution := Array.copy sol_incl
        );
        let bound_incl = compute_bound ks {
            level = next; value = v_incl; weight = w_incl;
            bound = 0.0; sol = sol_incl;
          } in
        if bound_incl > float_of_int !best_value then
          insert pq { level = next; value = v_incl; weight = w_incl;
                      bound = bound_incl; sol = sol_incl }
      )
  done;
  
  (* Return best solution *)
  !best_solution
    

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
  let bound = compute_bound ks {
      level = 4; value = 77; weight = 12;
      bound = 0.0; sol = [|1.;0.;1.;0.;1.|];
    } in
  Printf.printf "Value : %f \n" bound;
  let sol = binaryknapsack_bb sorted_ks in
  print_solution sorted_ks sol
