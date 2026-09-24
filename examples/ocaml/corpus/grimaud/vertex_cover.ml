(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Probleme_Couverture_de_sommets
   at commit e9cdc1970b4d:
   solutions/Grimaud_VertexCover.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

type vertex = int
type edge = vertex * vertex
type graph = {
  n : int;
  edges : edge list
}

type cover = vertex list

let print_cover (c : cover) : unit =
  Printf.printf "[";
  let rec aux i = function
    | [] -> ()
    | v :: rest ->
        if i > 0 then Printf.printf "; ";
        Printf.printf "%d" v;
        aux (i + 1) rest
  in
  aux 0 c;
  Printf.printf "]\n"
    

let is_vertex_cover (g : graph) (c : cover) : bool =
  (* Check if the edge (v, w) is covered by the vertex set c *)
  let edge_is_covered (v, w) =
    List.mem v c || List.mem w c
  in
  (* Every edge must be covered by at least one endpoint *)
  List.for_all edge_is_covered g.edges

let cover_of_mask (n : int) (mask : int) : cover =
  (* Build the list of vertices included in the mask *)
  let rec aux v acc =
    if v = n then acc
    else
      (* If bit v is set in mask, include vertex v in the cover *)
      let acc' = if (mask lsr v) land 1 = 1 then v :: acc else acc in
      aux (v + 1) acc'
  in
  aux 0 []


let exhaustive_vertex_cover (g : graph) : cover =
  (* Recursive helper to iterate over all masks *)
  let rec explore mask best =
    if mask = (1 lsl g.n) then best
    else
      let c = cover_of_mask g.n mask in
      if is_vertex_cover g c then
        match best with
        | None -> explore (mask + 1) (Some c)
        | Some b ->
          let best' =
            if List.length c < List.length b then
              Some c
            else
              best
          in
          explore (mask + 1) best'
      else
        explore (mask + 1) best
  in
  match explore 0 None with
  | None -> []
  | Some c -> c
    
let greedy_vertex_cover (g : graph) : cover =
  (* Recursive helper working on the list of remaining edges and the current cover *)
  let rec loop edges cover =
    match edges with
    | [] -> cover
    | (v, w) :: _ ->
      (* Add both endpoints of the chosen edge to the cover *)
      let cover' = v :: w :: cover in
      (* Remove all edges incident to v or w *)
      let edges' =
        List.filter
          (fun (x, y) -> x <> v && y <> v && x <> w && y <> w)
          edges
      in
      loop edges' cover'
  in
  (* Return the final cover *)
  loop g.edges []
 


let () =
  let g = {n=9;
           edges = [(0,1); (0,2);
                    (1,3); (1,4); (1,7);
                    (2,3); (2,5); (2,7);
                    (3,4); (3,5); (3,8);
                    (4,6);
                    (5,6);
                    (6,8)]} in
  let c = [0; 3; 4; 5; 6; 7] in
  print_cover c;
  Printf.printf "%B\n" (is_vertex_cover g c);
  print_cover (cover_of_mask g.n 249);
  print_cover (exhaustive_vertex_cover g);
  print_cover (greedy_vertex_cover g)
