(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch05_Algorithmes_sur_les_Graphes
   at commit c5684ef0538f:
   solutions/Kruskal/Grimaud_mergesort.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)


(* Merge two sorted arrays into one sorted array (purely functional) *)
let merge arr1 arr2 =
  let n1 = Array.length arr1 in
  let n2 = Array.length arr2 in
  let result = Array.make (n1 + n2) 0 in

  (* Recursive helper function *)
  let rec aux i j k =
    if i = n1 && j = n2 then result
    else if i = n1 then (
      result.(k) <- arr2.(j);
      aux i (j + 1) (k + 1)
    )
    else if j = n2 then (
      result.(k) <- arr1.(i);
      aux (i + 1) j (k + 1)
    )
    else if arr1.(i) <= arr2.(j) then (
      result.(k) <- arr1.(i);
      aux (i + 1) j (k + 1)
    )
    else (
      result.(k) <- arr2.(j);
      aux i (j + 1) (k + 1)
    )
  in
  aux 0 0 0


(* Recursive merge sort function *)
let rec merge_sort arr =
  let n = Array.length arr in
  if n <= 1 then arr
  else
    let mid = (n+1)/2 in
    let left = Array.sub arr 0 mid in
    let right = Array.sub arr mid (n - mid) in
    merge (merge_sort left) (merge_sort right)


(* Function to print an array *)
let print_array arr =
  Array.iter (fun x -> Printf.printf "%d " x) arr;
  Printf.printf "\n"

(* Example usage *)
let () =
  let arr = [|1;5;3;4;1;3;2;2;3;1;2;3;3;1|] in
  Printf.printf "Original array: ";
  print_array arr;
  let sorted = merge_sort arr in
  Printf.printf "Sorted array: ";
  print_array sorted
