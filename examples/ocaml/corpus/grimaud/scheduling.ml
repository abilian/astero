(* From "Informatique MPI", by Aslı Grimaud and Gilles Grimaud.
   https://github.com/Informatique-MPI/Probleme_Ordonnancement_des_taches
   at commit 8e6ac4bc42bf:
   solutions/Grimaud_Scheduling.ml
   GPL-3.0, see LICENSE in this directory. Unchanged below this comment. *)

(* A task is represented by an identifier and its processing time *)
type task = {
  id : int;   (* unique identifier of the task *)
  time : int; (* execution time of the task *)
}

(* A processor stores its identifier, its current workload and the list of assigned tasks *)
type processor = {
  id : int;          (* unique identifier of the processor *)
  load : int;        (* current accumulated execution time *)
  tasks : task list; (* tasks assigned to this processor *)
}

(* A scheduling is a list of processors *)
type scheduling = processor list

(* Create an initial scheduling with m empty processors.
   Each processor is initialized with a unique id, zero load,
   and an empty list of assigned tasks. *)
let init_processors m =
  List.init m (fun i -> { id = i; load = 0; tasks = [] })

(* Return the total execution time of a scheduling,
   defined as the maximum load among all processors. *)
let makespan (procs : scheduling) : int =
  List.fold_left (fun acc p -> max acc p.load) 0 procs

(*
let rec makespan = function
  | [] -> 0
  | [p] -> p.load
  | p :: ps ->
      let m = makespan ps in
      if p.load > m then p.load else m
*)

(* Print a single task as (id=X, time=Y) *)
let print_task (t : task) =
  Printf.printf "(id=%d, time=%d)" t.id t.time

(* Print a processor: its id, load, and the list of tasks it contains *)
let print_processor (p : processor) =
  Printf.printf "Proc %d (load=%d): [" p.id p.load;
  List.iter (fun t -> Printf.printf " "; print_task t) p.tasks;
  Printf.printf " ]\n"

(* Print a full scheduling: one processor per line *)
let print_scheduling (procs : scheduling) =
  Printf.printf "Scheduling with makespan=%d:\n" (makespan procs);
  List.iter print_processor procs

(* Return the list of tasks sorted in decreasing order of execution time *)
let sort_tasks (tasks : task list) : task list =
  List.sort
    (fun t1 t2 -> compare t2.time t1.time)
    tasks

(* Return one of the processors with the smallest load in the scheduling.
   Raises an exception if the list is empty. *)
let rec least_loaded = function
  | [] -> failwith "least_loaded: empty scheduling"
  | [p] -> p
  | p :: ps ->
      let q = least_loaded ps in
      if p.load < q.load then p else q

(* Return a new processor identical to p but with task t added *)
let assign_task (p : processor) (t : task) : processor =
  { p with
    load = p.load + t.time;
    tasks = t :: p.tasks }

(* Compute an LPT scheduling using m processors and the given list of tasks.
   Tasks are first sorted by decreasing duration, then assigned one by one
   to the currently least loaded processor. *)
let lpt (m : int) (tasks : task list) : scheduling =
  let rec assign_all procs tasks =
  match tasks with
  | [] -> procs
  | t :: ts ->
      let p = least_loaded procs in
      let others = List.filter (fun q -> q.id <> p.id) procs in
      let p_updated = assign_task p t in
      assign_all (p_updated :: others) ts
  in
  let sorted = sort_tasks tasks in
  let procs = init_processors m in
  assign_all procs sorted

(* Example main program: run LPT on the given task list and print the result *)
let () =
  (* Example tasks: [19; 12; 10; 8; 9; 15; 7; 2; 10; 13] *)
  let tasks = [
    {id=0; time=19};
    {id=1; time=12};
    {id=2; time=10};
    {id=3; time=8};
    {id=4; time=9};
    {id=5; time=15};
    {id=6; time=7};
    {id=7; time=2};
    {id=8; time=10};
    {id=9; time=13};
  ] in
  let m = 4 in
  let schedule = lpt m tasks in
  print_scheduling schedule
