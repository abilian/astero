(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch05_Algorithmes_sur_les_Graphes
   at commit c5684ef0538f:
   solutions/Kruskal/Union_find_impl.ml
   solutions/Kruskal/Grimaud_kruskal.ml
   GPL-3.0, see LICENSE in this directory.
   Changed: the body of module UnionFindRankPath from Union_find_impl.ml
   comes first, dedented, without its `module ... = struct ... end` wrapper
   and with a comment of two lines above it; the lines `open Union_find_impl`
   and `let open UnionFindRankPath in` are removed. The other two modules of
   Union_find_impl.ml, and Union_find.mli, are left out. *)

(* Union by rank and path compression: the body of
   [Union_find_impl.UnionFindRankPath], which [kruskal] opened. *)
type elt = int 
type uf = {
  parent: int array;
  rank: int array
}         
let create elements =
  let n = Array.length elements in
  {
    parent = Array.init n (fun i -> elements.(i));
    rank = Array.make n 0;
  }
let rec find uf x =
  if uf.parent.(x) = x then
    x
  else
    let root = find uf uf.parent.(x) in
    uf.parent.(x) <- root;
    root
let union uf x y =
  let cx = find uf x in
  let cy = find uf y in
  if cx <> cy then
    if uf.rank.(cx) < uf.rank.(cy) then
      uf.parent.(cx) <- cy
    else if uf.rank.(cy) < uf.rank.(cx) then
      uf.parent.(cy) <- cx
    else
      begin
        uf.parent.(cx) <- cy ;
        uf.rank.(cy) <- uf.rank.(cy) + 1
      end
let print_uf uf =
  Printf.printf "Parent : " ;
  Array.iter (fun x -> Printf.printf "%d " x) uf.parent ;
  Printf.printf "\n" ;
  Printf.printf "Rank   : " ;
  Array.iter (fun x -> Printf.printf "%d " x) uf.rank ;
  Printf.printf "\n"


type graph = float array array
    
type edge = {
  src : int;
  dst : int;
  weight : float
}

(* Merge two sorted arrays into one sorted array (purely functional) *)
let merge arr1 arr2 =
  let n1 = Array.length arr1 in
  let n2 = Array.length arr2 in
  let result = Array.make (n1 + n2) { src = 0; dst = 0; weight = 0.0 } in
  
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
    else if arr1.(i).weight <= arr2.(j).weight then (
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


let filter_some (arr: 'a option array) : 'a array =
  Array.of_list (List.filter_map (fun x -> x) (Array.to_list arr))

let kruskal (g: graph) : graph =
  let n = Array.length g in
  let size = (n * (n - 1)) / 2 in
  let edges = Array.make size None in
  let index i j = (i * (2 * n - i - 1)) / 2 + (j - i - 1) in
  for i = 0 to n - 1 do
    for j = i + 1 to n - 1 do
      let weight = g.(i).(j) in
      if weight <> 0. then
        edges.(index i j) <- Some { src = i; dst = j; weight = weight };
    done
  done;
  let g_edges = merge_sort (filter_some edges) in
  let uf = create (Array.init n (fun i -> i)) in
  let mst = Array.make_matrix n n 0.0 in
  for i=0 to Array.length g_edges -1 do
    let c_src = find uf g_edges.(i).src in
    let c_dst = find uf g_edges.(i).dst in
    if c_src <> c_dst then
      begin
        union uf c_src c_dst;
        let e = g_edges.(i) in
        mst.(e.src).(e.dst) <- e.weight;
        mst.(e.dst).(e.src) <- e.weight
      end
  done;
  mst

let print_graph (g : graph) =
  let n = Array.length g in
  for i = 0 to n - 1 do
    for j = 0 to Array.length g.(i) - 1 do
      Printf.printf "%.2f " g.(i).(j)
    done;
    Printf.printf "\n"
  done

let () =
  Printf.printf "Kruskal\n";
  (*let g = [|
    [|0.; 1.; 5.; 0.; 0.; 0.; 0.; 0.; 0.|];
    [|1.; 0.; 0.; 3.; 4.; 0.; 0.; 1.; 0.|];
    [|5.; 0.; 0.; 3.; 0.; 2.; 0.; 2.; 0.|];
    [|0.; 3.; 3.; 0.; 3.; 1.; 0.; 0.; 2.|];
    [|0.; 4.; 0.; 3.; 0.; 0.; 3.; 0.; 0.|];
    [|0.; 0.; 2.; 1.; 0.; 0.; 3.; 0.; 0.|];
    [|0.; 1.; 0.; 0.; 3.; 3.; 0.; 0.; 1.|];
    [|0.; 0.; 2.; 0.; 0.; 0.; 0.; 0.; 0.|];
    [|0.; 1.; 0.; 2.; 0.; 0.; 1.; 0.; 0.|]
    |] in
  *)
  
  let g = [|
    [|0.0; 2.4; 3.9; 1.0; 0.0; 0.0|];
    [|2.4; 0.0; 0.0; 4.1; 0.0; 0.0|];
    [|3.9; 0.0; 0.0; 3.3; 0.0; 0.0|];
    [|1.0; 4.1; 3.3; 0.0; 3.2; 4.6|];
    [|0.0; 0.0; 0.0; 3.2; 0.0; 4.6|];
    [|0.0; 0.0; 0.0; 4.6; 4.6; 0.0|]
  |] in
  (*
  let g = [|
    [|0.0; 3.2; 7.1; 0.0; 0.0; 0.0|];
    [|3.2; 0.0; 5.2; 4.8; 5.0; 0.0|];
    [|7.1; 5.2; 0.0; 0.0; 2.3; 2.2|];
    [|0.0; 4.8; 0.0; 0.0; 6.0; 0.0|];
    [|0.0; 5.0; 2.3; 6.0; 0.0; 3.7|];
    [|0.0; 0.0; 2.2; 0.0; 3.7; 0.0|]
  |] in
  *)
  let mst = kruskal g in
  print_graph mst
      
