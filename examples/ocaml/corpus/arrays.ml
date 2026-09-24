(* Arrays, loops, exceptions, strings. *)

let swap a i j =
  let tmp = a.(i) in
  a.(i) <- a.(j);
  a.(j) <- tmp

let bubble_sort a =
  let n = Array.length a in
  for i = 0 to n - 2 do
    for j = 0 to n - 2 - i do
      if a.(j) > a.(j + 1) then swap a j (j + 1)
    done
  done

let find_index p a =
  let n = Array.length a in
  let i = ref 0 in
  let found = ref (-1) in
  while !found < 0 && !i < n do
    if p a.(!i) then found := !i;
    incr i
  done;
  !found

let index_of c s =
  try
    for i = 0 to String.length s - 1 do
      if s.[i] = c then raise Exit
    done;
    -1
  with Exit -> 0

let () =
  let a = [| 4; 2; 9; 1 |] in
  bubble_sort a;
  Array.iter (fun x -> print_int x; print_char ' ') a
