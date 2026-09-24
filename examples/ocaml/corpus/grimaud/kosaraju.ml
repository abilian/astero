(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Ch05_Algorithmes_sur_les_Graphes
   at commit c5684ef0538f:
   solutions/Kosaraju/Grimaud_Kosaraju.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

type graph = int list array

let depth_first_search_preorder (g : graph) =
  let n = Array.length g in
  let marked = Array.make n false in
  let dfs_stack = Stack.create () in

  (* Recursive function to explore the graph *)
  let rec explore v =
    if not marked.(v) then begin
      marked.(v) <- true;
      (* push in prefix order *)
      Stack.push v dfs_stack;
      (* Explore all neighbors *)
      List.iter explore g.(v) 
    end
  in
  
  (* Extract the prefix order from the stack *)
  let rec extract_dfs acc =
    if Stack.is_empty dfs_stack then acc
    else extract_dfs (Stack.pop dfs_stack :: acc)
  in

  (* Start DFS for all nodes in order *)
  List.iter (fun v ->
    if not marked.(v) then explore v
  ) (List.init n (fun i -> i));
  extract_dfs []

let depth_first_search_postorder (g : graph) =
  let n = Array.length g in
  let marked = Array.make n false in
  let dfs_stack = Stack.create () in

  (* Recursive function to explore the graph *)
  let rec explore v =
    if not marked.(v) then begin
      marked.(v) <- true;
      (* Explore all neighbors *)
      List.iter explore g.(v);
      (* push in postfix order *)
      Stack.push v dfs_stack 
    end
  in

  (* Extract the post order from the stack *)
  let rec extract_dfs acc =
    if Stack.is_empty dfs_stack then acc
    else extract_dfs (Stack.pop dfs_stack :: acc)
  in
  
  (* Start DFS for all nodes in order *)
  List.iter (fun v ->
    if not marked.(v) then explore v
  ) (List.init n (fun i -> i));
  extract_dfs []

let transposed_graph (g : graph) : graph =
  let n = Array.length g in
  let tr = Array.make n [] in
  
  (* Iterate over each vertex and its neighbors to reverse edges *)
  Array.iteri (fun v neighbors ->
    List.iter (fun w -> tr.(w) <- v :: tr.(w)) neighbors
  ) g;
  tr


let depth_first_search_components (g : graph) (order : int list) =
  let n = Array.length g in
  let marked = Array.make n false in
  let dfs_stack = Stack.create () in

  (* Recursive function to explore the graph *)
  let rec explore v =
    if not marked.(v) then begin
      marked.(v) <- true;
      (* push in preorder *)
      Stack.push v dfs_stack;
      (* Explore all neighbors *)
      List.iter explore g.(v) 
    end
  in

  (* Extract the postorder order from the stack *)
  let rec extract_dfs acc =
    if Stack.is_empty dfs_stack then acc
    else extract_dfs (Stack.pop dfs_stack :: acc)
  in
  
  (* Main loop over vertices in the given order *)
  let rec loop comps order = 
    match order with
    | [] -> comps
    | v :: vs ->
        if marked.(v) then
          loop comps vs
        else begin
          explore v;
          let comp = extract_dfs [] in
          loop (comp :: comps) vs
        end
  in
  loop [] order

let kosaraju (g : graph) =
  let order = List.rev (depth_first_search_postorder g) in
  let tr_g = transposed_graph g in
  depth_first_search_components tr_g order

let () =
  (* Exemple application TD TP *)
  
  let g = [|
    (* 0 *) [1; 8];  
    (* 1 *) [2];    
    (* 2 *) [3; 7; 8];  
    (* 3 *) [4; 6];  
    (* 4 *) [3; 5];    
    (* 5 *) [4; 6];     
    (* 6 *) [7];  
    (* 7 *) [6];
    (* 8 *) [1; 7]
  |] in
  
  (* Exemple 2SAT TD TP *)
  (* 
  let g = [|
    (* 0 *) [1];  
    (* 1 *) [9];    
    (* 2 *) [];  
    (* 3 *) [0; 1; 2];  
    (* 4 *) [6];    
    (* 5 *) [2; 8];     
    (* 6 *) [4; 5; 8];  
    (* 7 *) [0; 8];
    (* 8 *) [4];
    (* 9 *) [1; 3]
    |] in
  *)
  let sccs = kosaraju g in
  Printf.printf "Strongly connected components :\n";
  List.iter (fun scc ->
      Printf.printf "- { %s }\n"
        (String.concat ", " (List.map string_of_int scc))
    ) sccs;
  print_newline ();

  let dfs_preorder = depth_first_search_preorder g in
  let dfs_postorder = depth_first_search_postorder g in

  Printf.printf "DFS preorder from 0: %s\n"
    (String.concat " " (List.map string_of_int dfs_preorder));

  Printf.printf "DFS postorder from 0: %s\n"
    (String.concat " " (List.map string_of_int dfs_postorder));


