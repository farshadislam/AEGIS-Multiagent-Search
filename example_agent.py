from typing import List, Dict, Tuple, Optional, override

# If you need to import anything else, add it to the import below.

from aegis import (
    END_TURN,
    MOVE,
    SAVE_SURV,
    SEND_MESSAGE,
    SEND_MESSAGE_RESULT,
    TEAM_DIG,
    AgentCommand,
    AgentIDList,
    AgentID,
    World,
    Cell,
    Direction,
    Rubble,
    Survivor,
    Location,
    create_location,
    SLEEP,
)
from mas.agent import BaseAgent, Brain, AgentController
import heapq
import random


class ExampleAgent(Brain):
    # Store any constants you want to define here
    # Example:
    NUM_AGENTS = 4

    def __init__(self) -> None:
        super().__init__()
        self._agent: AgentController = BaseAgent.get_agent()
        
        # Initalize any variables or data structures here
        # Some potentially useful suggestions:
        # self._locs_with_survs_and_amount: dict[Location, int] = {}
        # self._visited_locations: set[Location] = set()
        self._best_path: List[Direction] = [] # Series of directions
        self._goal_loc: Optional[Tuple[int, int]] = None # My own location object, seeing as how we cannot import Location for this assignment
        self._explored_cells: Dict[Tuple[int, int], int] = {}  # Stores known move costs for each cell
        self._agent_energy = self._agent.get_energy_level()  # Track agent's remaining energy (typically 500 given the examples)

        self._agent_locations: Dict[int, Location] = {}
        self._danger_cells = set()  # Set to track dangerous cells {(x, y)} (Killer and Fire)
        self._charging_cells = set() # Tracks all charging cells 
        self._survivor_cells = set() # Tracks cells containing a survivor

        self._current_goal = None
        self._agent_groups: Dict[int, List[int]] = {} # Maps group ID -> group members
        self._group_goals: Dict[int, Location] = {} # Maps group ID -> assigned goal location


    @override
    def handle_send_message_result(self, smr: SEND_MESSAGE_RESULT) -> None:
        # This runs whenever a message is recieved by this agent. Messages are recieved one round after they are sent.
        # Figure out some way to identify what the message is about/what info it contains, and process it accordingly.
        # smr.msg stores the string containing the message

        self._agent.log(f"SEND_MESSAGE_RESULT: {smr}")

        # Below is an example of how you could structure your message handling.
        # For this approach, your message consists of a message type string followed by numeric information (e.g. coordinates)
        # Different parts of the message are split by spaces so we can easily separate them

        # Example message: receiving "MOVE 2 1" tells this agent to move to Location (2, 1)

        # We can start by splitting the message components into a list of strings based on spaces
        msg_list = smr.msg.split()

        if msg_list[0] == "GOAL":
            location = create_location(int(msg_list[1]), int(msg_list[2]))
            self._current_goal = location

            # Log the received message and the agent's location.
            self._agent.log(f"Agent {self._agent.get_agent_id().id} rescuing survivor at location: {location}")

        elif msg_list[0] == "REPORT_LOCATION":
                # Handle report message.
                agent_id = int(msg_list[1])
                location_x = int(msg_list[2])
                location_y = int(msg_list[3])
                location = create_location(location_x, location_y)
                self._agent_locations[agent_id] = location # Add location to a dictionary where all agents are located
                self._agent.log(f"Agent {agent_id}'s location at ({location})")

                # Leader pairs agents once all have been identified and round 2 has started
                if self._agent.get_agent_id().id == 1 and self._agent.get_round_number() == 2:
                    self.assign_groups()
                    self.assign_group_goals()
        
        elif msg_list[0] == "SAVING":
            surv_x = int(msg_list[1])
            surv_y = int(msg_list[2])
            surv_loc = create_location(surv_x, surv_y)

            self._survivor_cells.discard(surv_loc)
            self.assign_group_goals()

        else:
            # A message was sent that doesn't match any of our known formats
            self._agent.log(f"Unknown message format: {smr.msg}")
        

    @override
    def think(self) -> None:
        self._agent.log("Thinking...")
        self._agent.send(SEND_MESSAGE(AgentIDList(), f"REPORT_LOCATION {self._agent.get_agent_id().id} {self._agent.get_location().x} {self._agent.get_location().y}"))

        world = self.get_world()
        grid = world.get_world_grid()

        if world is None:
            self._agent.log(f"World not found!")
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return

        # First round initialization
        if self._agent.get_round_number() == 1:
            if self._agent.get_agent_id().id == 1:
            # Analyze all cells for special properties
                for y in range(len(grid)):  
                    for x in range(len(grid[0])): 
                        cell = grid[y][x] 
                        if cell is None:  # Skip if the cell is unknown
                            continue
                        # Check if the top layer of the cell is a Survivor
                        if cell.has_survivors:
                            self._survivor_cells.add(cell.location)
                            self._agent.log(f"Survivor found at ({cell.location.x}, {cell.location.y})") 

                        # If this cell is dangerous, add to danger set
                        if cell.is_fire_cell() or cell.is_killer_cell():
                            self._danger_cells.add(cell.location)
                            self._agent.log(f"Danger found at ({cell.location.x}, {cell.location.y})")

                        # If this cell is charging, add to charging cell set      
                        if cell.is_charging_cell():
                            self._charging_cells.add(cell.location)
                            self._agent.log(f"Charging cell found at ({cell.location.x}, {cell.location.y})")

                # Log all discovered cells
                self._agent.log(f"Total survivors cells: {len(self._survivor_cells)} | {self._survivor_cells}")
                self._agent.log(f"Total dangerous cells: {len(self._danger_cells)} | {self._danger_cells}")
                self._agent.log(f"Total charging cells: {len(self._charging_cells)} | {self._charging_cells}")

            #self.send_and_end_turn(MOVE(Direction.CENTER))
            self._agent.send(END_TURN())  # End turn after initialization
            return

        # Check if already on survivor
        current_cell = world.get_cell_at(self._agent.get_location())
        if current_cell and isinstance(current_cell.get_top_layer(), Survivor):
            self._agent.send(SEND_MESSAGE(AgentIDList(), f"SAVING {current_cell.location.x} {current_cell.location.y}"))
            self.send_and_end_turn(SAVE_SURV())
            return

        elif current_cell and current_cell.has_survivors:
            top_layer = current_cell.get_top_layer()

            if isinstance(top_layer, Rubble):
                self.clear_rubble(current_cell, self._agent.get_location())
                return
            else:
                self._agent.save_survivor()
                return

        

        start_loc = self._agent.get_location()
        new_goal_loc = self._current_goal

        if not new_goal_loc:
            self._agent.log("No current goal set, waiting for assignment.")
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return

        # Finds a path to the survivor if there isn't one already, every turn
        survivor_path = self.a_star_search(world, start_loc, new_goal_loc) # A* search algorithm which returns a series of directions for the agent to reach the survivor
        self._current_goal = self.goal_priority(world, current_cell, survivor_path, new_goal_loc) # Stores the best path to the survivor in a list of directions
        #print("Current goal:", world.get_cell_at(self._current_goal).is_charging_cell())
        self._best_path = self.a_star_search(world, start_loc, new_goal_loc)#self._current_goal)

        print(self._agent.get_energy_level() < self.get_move_cost_path(world, current_cell, survivor_path), self.get_move_cost_path(world, current_cell, survivor_path))
        print(self._agent.get_energy_level(), "Agent energy level")
        if current_cell and current_cell.is_charging_cell() and self._agent.get_energy_level() <= self.get_move_cost_path(world, current_cell, survivor_path):
            # If the agent is on a charging cell and doesn't have enough energy to reach the survivor, charge
            print("GO THE FUCK TO SLEEP")
            self.send_and_end_turn(SLEEP())

        # Move along path
        if len(self._best_path) > 0:
            next_dir = self._best_path.pop(0) # Pops next direction for the agent to move in
            self.send_and_end_turn(MOVE(next_dir)) # Moves agent in said direction
        else:
            self.send_and_end_turn(MOVE(Direction.CENTER))

        # if self._agent_energy < 50:
        #     return

    def a_star_search(self, world, start_loc, goal_loc_obj) -> List[Direction]:
        # Priority queue: (priority, tie_breaker, location)
        to_visit = [] # Priority queue keeping track of locations, with built-in tie breaker implementation
        heapq.heappush(to_visit, (0, 0, start_loc)) # Has priority, tie breaker for same priorities, and the location
        visited: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {} # Dictionary tracking locations and how they were reached
        track_costs: Dict[Tuple[int, int], int] = {} # Keeps track of costs to reach every cell every time a_star_search() is called
        visited[(start_loc.x, start_loc.y)] = None # We started at the starting location, we didn't get there from anywhere
        track_costs[(start_loc.x, start_loc.y)] = 0 # Cost to reach the starting position is zero
        tie_breaker = 1 # This value will be incremented iff two values are given the same priority

        while to_visit: # This is done so long as the to_visit list is not empty
            _, _, current_loc = heapq.heappop(to_visit) # Get the highest priority location from to_visit
            current_coords = (current_loc.x, current_loc.y) # Get the specific x and y values for the location

            if current_coords == (goal_loc_obj.x, goal_loc_obj.y): # Ends function call is the survivor cell is reached
                return self.reconstruct_path(visited, start_loc, current_loc) # Returns calculated path to survivor

            for direction in Direction: # Observes all adjacent cells from current cell
                if direction == Direction.CENTER: # Skips current cell obsesrvation
                    continue

                neighbor_loc = current_loc.add(direction) # Gets location of adjacent cell
                neighbor_coords = (neighbor_loc.x, neighbor_loc.y) # Stores the location in my own tuple structure
                
                if not self.is_valid_move(world, neighbor_loc): # Can't be a killer, fire, or high cost cell
                    continue

                # Calculate new cost
                new_move_cost = world.get_cell_at(neighbor_loc).move_cost # Cost of neighbour cell
                new_cost = track_costs[current_coords] + new_move_cost # Overrall cost to reach neighbour cell

                if (neighbor_coords not in track_costs or new_cost < track_costs[neighbor_coords]): # Logic to add a possible path-intermediate
                    track_costs[neighbor_coords] = new_cost # Reassigns cost of cell
                    cheb_heuristic = max(abs(goal_loc_obj.x - neighbor_loc.x), abs(goal_loc_obj.y - neighbor_loc.y)) # Generates heuristic based on Chebychev distance between survivor location and neighbour location
                    priority = new_cost + cheb_heuristic # Priority of cell based on overall cost to reach and heuristic
                    heapq.heappush(to_visit, (priority, tie_breaker, neighbor_loc)) # Push new location to the priority queue
                    tie_breaker += 1 # Every location added is numbered, so if two equal priority locations occur, there's not gonna be a tussle over who gets popped
                    visited[neighbor_coords] = current_coords # Neighbour is reachable from the current location

        return []  # No path found

    def is_valid_move(self, world, location) -> bool:
        if not world.on_map(location): # Check if location is on the grid
            return False
            
        cell = world.get_cell_at(location) # CHeck if there is a cell at the location
        if not cell:
            return False 
            # Skip charging cells if agent has enough energy
        if cell.is_charging_cell() and self._agent.get_energy_level() > 50:
            return False

            
        return not cell.is_killer_cell() and not cell.is_fire_cell() and cell.move_cost < self._agent.get_energy_level()  # CHecks for dangerous or high cost cells and avoids them

    def reconstruct_path(self, visited, start_loc, end_loc) -> List[Direction]: # Take visited dictionary, start and end locations 
        path = [] # Series of directions that will be returned in think()
        current_coords = (end_loc.x, end_loc.y) # Start at the end
        start_coords = (start_loc.x, start_loc.y) # Want to reach the beginning of the agent's path
        
        while current_coords != start_coords:
            prev_coords = visited[current_coords] # Access location current coordinate was reached from
            prev_loc = create_location(prev_coords[0], prev_coords[1]) # Make into Location object
            current_loc = create_location(current_coords[0], current_coords[1]) # Make into Location object
            direction = prev_loc.direction_to(current_loc) # Get the direction between the two locations
            path.append(direction) # Add the direction to the path
            current_coords = prev_coords # Reassign the current coordinates and then do it all over, until the current coordinates match the starting coordinates
            
        return path[::-1]  # Reverse to get start-to-end order
    
    def assign_groups(self) -> None:
        # Include the leader (ID 1) and agents who reported location
        all_agents = sorted(set(self._agent_locations.keys()) | {1})

        group_id = 1
        num_agents = len(all_agents)

        for i in range(0, num_agents - 1, 2):  # Group in pairs
            id1 = all_agents[i]
            id2 = all_agents[i + 1]

            self._agent_groups[group_id] = [id1, id2]
            self._agent.log(f"Paired Agent {id1} with Agent {id2} in group {group_id}")
            group_id += 1

        # If there's an unpaired agent, add them to the last group
        if num_agents % 2 == 1:
            leftover_id = all_agents[-1]
            if self._agent_groups:
                random_group = random.choice(list(self._agent_groups.keys()))
                self._agent_groups[random_group].append(leftover_id)
                self._agent.log(f"Added Agent {leftover_id} to group {random_group}, making it a group of 3")
            else:
                self._agent.log(f"Only one agent ({leftover_id}), no groups to add them to")

    def assign_group_goals(self) -> None:
        if not self._agent_groups or not self._survivor_cells:
            self._agent.log("No groups or survivors to assign.")
            return

        unassigned_survivors = set(self._survivor_cells) # Copy 

        for group_id, agent_ids in self._agent_groups.items():
            best_survivor = None
            min_path_len = float('inf')

            # Use the first agent in the group as a representative
            representative_id = agent_ids[0]
            agent_loc = self._agent_locations.get(representative_id)

            if not agent_loc:
                self._agent.log(f"Location of Agent {representative_id} unknown, skipping group {group_id}")
                continue

            for survivor in unassigned_survivors:
                path = self.a_star_search(self.get_world(), agent_loc, survivor)
                if path and len(path) < min_path_len:
                    min_path_len = len(path)
                    best_survivor = survivor

            if best_survivor:
                self._group_goals[group_id] = best_survivor
                unassigned_survivors.remove(best_survivor)

                goal_msg = f"GOAL {best_survivor.x} {best_survivor.y}"
                for aid in agent_ids:
                    self._agent.send(SEND_MESSAGE(AgentIDList([AgentID(aid, self._agent.get_agent_id().gid)]), goal_msg))
                self._agent.log(
                    f"Assigned survivor at ({best_survivor.x}, {best_survivor.y}) to group {group_id} "
                    f"with estimated path length {min_path_len}"
                )
            else:
                self._agent.log(f"No reachable survivor for group {group_id}")

    def recover_energy_priority(self):
        return 

    def clear_rubble(self, cell: Cell, current_loc: Location):

        if not cell or not isinstance(cell.get_top_layer(), Rubble):
            self._agent.log("No rubble to clear at current location.")
            return

        rubble: Rubble = cell.get_top_layer()
        agents_needed = rubble.remove_agents
        energy_needed = rubble.remove_energy
        current_agents = cell.agent_id_list.size()

        self._agent.log(
            f"Rubble found at ({current_loc.x}, {current_loc.y})"
            f"Needs {agents_needed} agents and {energy_needed} energy."
      
        )

        if agents_needed >= current_agents:
            self._agent.log(f"Agent {self._agent.get_agent_id().id} clearing rubble at ({current_loc.x}, {current_loc.y}) with team")
            self.send_and_end_turn(TEAM_DIG())
            
        else:
            self._agent.log(
                f"Not enough agents to clear rubble at ({current_loc.x}, {current_loc.y})."
            )

    def get_move_cost_path(self, world: World, current_cell: Cell, survivor_path: List[Direction]) -> int:
        """Check if the agent has enough energy to perform actions."""
        # Checking if agent has enough energy to move to survivor cell
        cell = None # Initialize cell variable to None
        a_star_move_cost = current_cell.move_cost # Initialize move cost for the path to the survivor cell
        for direction in survivor_path: # If the agent has a path to the survivor, check if it has enough energy to move
            if direction == Direction.CENTER:
                    continue
            if cell is not None:
                cell = world.get_cell_at(create_location(cell.location.x, cell.location.y).add(direction)) # getting the adjacent cell's adjacent cells
            else:
                cell = world.get_cell_at(create_location(current_cell.location.x, current_cell.location.y).add(direction)) # getting the adjacent cell's adjacent cells
            a_star_move_cost += cell.move_cost
        #print(a_star_move_cost, "Move cost for the path to the survivor cell")
        return a_star_move_cost  # Returns the move cost for the path to the survivor cell
    
    def goal_priority(self, world, current_cell, survivor_path, survivor_goal) -> Location:
        """Check if the agent has enough energy to perform actions."""
        # Checking if agent has enough energy to move to survivor cell
        cell = None # Initialize cell variable to None
        a_star_move_cost = 0 # Initialize move cost for the path to the survivor cell
        for direction in survivor_path: # If the agent has a path to the survivor, check if it has enough energy to move
            if direction == Direction.CENTER:
                    continue
            if cell is not None:
                cell = world.get_cell_at(create_location(cell.location.x, cell.location.y).add(direction)) # getting the adjacent cell's adjacent cells
            else:
                cell = world.get_cell_at(create_location(current_cell.location.x, current_cell.location.y).add(direction)) # getting the adjacent cell's adjacent cells
            a_star_move_cost += cell.move_cost
        
        if self._agent.get_energy_level() < a_star_move_cost: # If the agent does not have enough energy to move to the survivor cell
            #print("Low energy, looking for charging cell.")
            #self.send_and_end_turn(SEND_MESSAGE(AgentIDList(), f"LOW_ENERGY {self._agent.get_agent_id().id} {current_cell.location.x} {current_cell.location.y}"))
            #self._agent.send(SEND_MESSAGE(AgentIDList(), f"LOW_ENERGY {self._agent.get_agent_id().id} {current_cell.location.x} {current_cell.location.y}"))
            

            agent_location = self._agent.get_location()
            # Getting the move costs of all the charging cells before moving towards the one with the lowest cost
            charging_cells = [] # List will store tuples of (Location charge_goal, int move_cost, path List[Direction])
            for charge_cell in self._charging_cells:
                a_star_path = self.a_star_search(world, self._agent.get_location(), charge_cell)
                a_star_move_cost = 0 # Initialize move cost for the path to the charging cell
                cell = None
                for direction in a_star_path:
                    if direction == Direction.CENTER:
                        continue
                    if cell is not None:
                        cell = world.get_cell_at(create_location(cell.location.x, cell.location.y).add(direction)) # getting the adjacent cell's adjacent cells
                    else:
                        cell = world.get_cell_at(create_location(agent_location.x, agent_location.y).add(direction)) # getting the adjacent cell's adjacent cells
                    a_star_move_cost += cell.move_cost
                charging_cells.append((charge_cell, a_star_move_cost, a_star_path)) # Add the path ID, move cost, and path to the list
            # Sort the charging cells by move cost
            charging_cells.sort(key=lambda x: x[1]) # Sorts the list of tuples by move cost

            charging_goal = []
            if charging_cells: # If there are charging cells available
                charging_goal = charging_cells[0][0] # Gets the location of the charging cell with the lowest move cost
                self._agent.log(f"Charging cell with lowest move cost is {charging_goal} with a move cost of {charging_cells[0][1]}.")  
                return charging_goal
                # Move towards the charging cell
                charging_path = charging_cells[0][2] # Gets the path to the charging cell with the lowest move cost
                #self._current_goal = charging_goal # Sets the current goal to the charging cell with the lowest move cost
        else:
            return survivor_goal

    def send_and_end_turn(self, command: AgentCommand):
        """Send a command and end your turn."""
        self._agent.log(f"SENDING {command}")
        self._agent.send(command)
        self._agent.send(END_TURN())