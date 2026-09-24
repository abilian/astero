(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch03_Algorithmes_Probabilites_et_d_Approximation
   at commit dfc6e56eebc3:
   solutions/Quickselect/Grimaud_quickselect.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

let rec quickselect list k =
  match list with
  | [] -> failwith "Empty list"  (* Should not occur *)
  | [x] -> x
  | _ ->
      let pivot = List.nth list (Random.int (List.length list)) in
      let lower = List.filter (fun x -> x < pivot) list in
      let higher = List.filter (fun x -> x > pivot) list in
      let equal = List.filter (fun x -> x = pivot) list in
      let len_lower = List.length lower in
      let len_equal = List.length equal in
      if k <= len_lower then
        quickselect lower k
      else if k <= len_lower + len_equal then
        pivot
      else
        quickselect higher (k - len_lower - len_equal)

let () =
  Random.self_init ();
  let l = [7; 2; 1; 6; 6; 5; 3; 4] in
  let k = 8 in
  let result = quickselect l k in
  Printf.printf "The %d-th smallest element is: %d\n" k result
