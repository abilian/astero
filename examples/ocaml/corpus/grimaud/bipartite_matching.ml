(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch05_Algorithmes_sur_les_Graphes
   at commit c5684ef0538f:
   solutions/Matching/Grimaud_matching.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

type graph = int list array
    
type bipartite_graph = {
  edges : int list array;
  v1 : int list;
  v2 : int list
}

(* matching.(u) = the vertex matched with u, or -1 if u is unmatched *)
type matching = int array

type path = int list option

let augmenting_graph (g:bipartite_graph) (m: matching) : graph =
  let n = Array.length g.edges in
  let source = n in   (* Source vertex (n) *)
  let sink = n + 1 in (* Sink vertex (n+1) *)
  let g_m = Array.make (n+2) [] in

  (* Iterate over v1 *)
  List.iter (fun u ->
      List.iter (fun v ->
          if m.(u) <> v then
            g_m.(u) <- v :: g_m.(u)
        ) g.edges.(u)
    ) (g.v1);
  
  (* Iterate over v2 *)
  List.iter (fun u ->
      if m.(u) <> -1 then
        g_m.(u) <- m.(u) :: g_m.(u)
    ) (g.v2);  
  
  (* Add edges from the source to all free nodes in v1 *)
  List.iter (fun u ->
      if m.(u) = -1 then
      g_m.(source) <- u :: g_m.(source)  (* Source -> u *)
    ) g.v1;
  
  (* Add edges from all free nodes in v2 to the sink *)
  List.iter (fun v ->
    if m.(v) = -1 then
      g_m.(v) <- sink :: g_m.(v)  (* v -> Sink *)
  ) g.v2;

  g_m

let find_directed_path (g: graph) (s:int) (t:int) : path =
  let n = Array.length g in
  let marked = Array.make n false in
  let parent = Array.make n (-1) in
  let rec explore v =
    if not marked.(v) then
      begin
        marked.(v) <- true;
        if (v <> t) then
          List.iter (fun neighbor ->
              if not marked.(neighbor) then
                begin
                  parent.(neighbor) <- v; 
                  explore neighbor
                end
            ) g.(v)
      end
  in
  explore s;
  (* If t is not reached, return None *)
  if parent.(t) = -1 then
    None
  else
    begin
      (* Reconstruct path by backtracking from t to s *)
      let rec reconstruct_path acc node =
        if node = -1 then
          acc
        else
          reconstruct_path (node :: acc) parent.(node)
      in
      Some (reconstruct_path [] t)
    end

let print_matching (m:matching) =
  Array.iter (Printf.printf "%d ") m;
  print_newline()

let find_augmenting_path (g:bipartite_graph) (m:matching) : path = 
  let ag = augmenting_graph g m in
  let s = Array.length g.edges in
  let t = Array.length g.edges+1 in
  let path = find_directed_path ag s t in
  match path with
  | Some p ->
    begin
      match p with
      | [] | [_] | [_; _] -> Some []  
      | _ ->
        let first = List.hd p in
        let last = List.hd (List.rev p) in
        (* List.iter (fun x-> Printf.printf "%d " x) p; print_newline(); *)
        Some (List.filter (fun x -> x <> first && x <> last) p)
    end
  | None -> None
    

let update_matching (m:matching) (aug_path: path) : matching =
  let new_m = Array.copy m in
  let rec flip_edges p =
    match p with
    | [] | [_] -> ()
    | u :: v :: tail -> new_m.(u) <- v; new_m.(v) <- u; flip_edges tail
  in
  begin
    match aug_path with
    | None -> failwith "None augmenting path found"
    | Some path -> flip_edges path
  end;
  new_m
  
let maximum_matching (g:bipartite_graph) : matching =
  let n = Array.length g.edges in
  let m = Array.make n (-1) in
  let rec aux m =
    let aug_path = find_augmenting_path g m in
    match aug_path with
    | Some p -> (* print_matching m; *) aux (update_matching m aug_path)
    | None -> m
  in
  aux m

type b_graph = bool array array

let convert (g:b_graph) : bipartite_graph =
  let rows = Array.length g in
  let cols = if rows = 0 then 0 else Array.length g.(0) in
  let edges = Array.make rows [] in 
  for i = 0 to rows - 1 do
    for j = 0 to cols - 1 do
      if g.(i).(j) then
        begin
          edges.(i) <- (j+rows) :: edges.(i);
          edges.(j+rows) <- i :: edges.(j+rows)
        end
    done;
  done;
  { edges;
    v1 = List.init rows (fun i -> i);
    v2 = List.init cols (fun i -> i+rows) }


let () =
  (* Graphe du cours *)
  let g = {
    edges = [|
      [8; 12];             (* 0 *)
      [8; 10];             (* 1 *)
      [7; 9; 11];          (* 2 *)
      [7; 9; 11];          (* 3 *)
      [8; 10; 12];         (* 4 *)
      [9; 10; 11; 12; 13]; (* 5 *)
      [12];                (* 6 *)
      [2; 3];              (* 7 *)
      [0; 1; 4];           (* 8 *)
      [2; 3; 5];           (* 9 *)
      [1; 4; 5];           (* 10 *)
      [2; 3; 5];           (* 11 *)
      [0; 4; 5; 6];        (* 12 *)
      [5]                  (* 13 *)
    |];
    v1 = [0; 1; 2; 3; 4; 5; 6];  (* Partition 1 *)
    v2 = [7; 8; 9; 10; 11; 12; 13]   (* Partition 2 *)
  } in
  (* Graphe du TD/TP *)
  let g = {
    edges = [|
      [7; 11];     (* 0 *)
      [7; 8; 9];   (* 1 *)
      [9];         (* 2 *)
      [9; 10];     (* 3 *)
      [7; 9; 12];  (* 4 *)
      [10; 13];    (* 5 *)
      [9; 12; 13]; (* 6 *)
      [0; 1];      (* 7 *)
      [1];         (* 8 *)
      [2; 3; 4];   (* 9 *)
      [3];         (* 10 *)
      [0];         (* 11 *)
      [4; 6];      (* 12 *)
      [6]          (* 13 *)
    |];
    v1 = [0; 1; 2; 3; 4; 5; 6];  (* Partition 1 *)
    v2 = [7; 8; 9; 10; 11; 12; 13]   (* Partition 2 *)
  } in
  (* matching *)
  (* let m = [|-1; 10; -1; 9; -1; 11; 12; -1; -1; 3; 1; 5; 6; -1|] in*)
  let m = maximum_matching g in
  print_matching m

