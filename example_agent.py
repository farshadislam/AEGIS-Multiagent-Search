from typing import List, Dict, Tuple, Optional, override

# If you need to import anything else, add it to the import below.
from special_locations import (
    add_danger,
    add_heal,
    add_survivor,
)

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


class ExampleAgent(Brain):
    # Store any constants you want to define here
    # Example:
    NUM_AGENTS = 7

    def __init__(self) -> None:
        super().__init__()
        self._agent: AgentController = BaseAgent.get_agent()
        
        # Initalize any variables or data structures here
        # Some potentially useful suggestions:
        # self._locs_with_survs_and_amount: dict[Location, int] = {}
        # self._visited_locations: set[Location] = set()
        self._best_path: List[Direction] = [] # Series of directions
        self._goal_loc: Location = None # My own location object, seeing as how we cannot import Location for this assignment
        self._explored_cells: Dict[Location, int] = {}  # Stores known move costs for each cell
        self._agent_energy = self._agent.get_energy_level()  # Track agent's remaining energy (typically 500 given the examples)

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

        if msg_list[0] == "MOVE":
            # Extract the location from the rest of the message
            # Remember to convert numbers from a strings to integers
            location_x = int(msg_list[1])
            location_y = int(msg_list[2])
            # Create a Location object from the extracted coordinates.
            location = create_location(location_x, location_y)

            self._current_goal = location

            # Log the received message and the agent's location.
            self._agent.log(f"Agent {self._agent.get_agent_id().id} is heading to location: {location}")
        elif msg_list[0] == "LOCATION": # Handles messages formatted with "LOCATION x y : agent_id"
            # Extract the agent ID and its location from the message
            location_x = int(msg_list[1])
            location_y = int(msg_list[2])
            agent_id = int(msg_list[4]) 
            location = create_location(location_x, location_y)

            # Store the agent's location in a data structure (e.g., a list or dictionary)
            # Here we assume you have a list of agent locations initialized in __init__
            #if 0 < agent_id <= self.NUM_AGENTS:
            self._agent_locations[agent_id-1] = location
            
            # for ids in self._agent_locations:
            #     print(ids)
            self._agent.log(f"Agent {agent_id} is at {location}")
            #else:
                #self._agent.log(f"Received location for unknown agent ID: {agent_id}")

        # you can add cases for other types of messages here

        elif msg_list[0] == "SAVING": # Handles messages formatted with "SAVING x y : agent_id"
            location_x = int(msg_list[1])
            location_y = int(msg_list[2])
            agent_id = int(msg_list[4])
            location = create_location(location_x, location_y)

        else:
            # A message was sent that doesn't match any of our known formats
            self._agent.log(f"Unknown message format: {smr.msg}")

    @override
    def think(self) -> None:
        self._agent.log("Thinking...")

        # First round initialization
        if self._agent.get_round_number() == 1:
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return

        # Get the world object to perform operations upon
        world = self.get_world()
        if world is None:
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return

        # Check if already on survivor
        current_cell = world.get_cell_at(self._agent.get_location())
        if current_cell and isinstance(current_cell.get_top_layer(), Survivor):
            self.send_and_end_turn(SAVE_SURV())
            return

        # Finds a path to the survivor if there isn't one already, every turn
        self._best_path = self.a_star_search(world) # A* search algorithm which returns a series of directions for the agent to reach the survivor

        # Move along path
        if len(self._best_path) > 0:
            next_dir = self._best_path.pop(0) # Pops next direction for the agent to move in
            self.send_and_end_turn(MOVE(next_dir)) # Moves agent in said direction
        else:
            self.send_and_end_turn(MOVE(Direction.CENTER))

    def a_star_search(self, world, goal_loc_obj) -> List[Direction]:
        start_loc = self._agent.get_location() # Gets initial starting position of agent at the beginning of the simulation
        
        '''
        if not self._goal_loc: # Identifies that there is not currently a goal location
            for y in range(world.height):
                for x in range(world.width): # Iterates through entire grid searching for a survivor
                    loc = create_location(x, y) # Makes a location inside the grid
                    cell = world.get_cell_at(loc) # Observes the cell at that location
                    if cell.has_survivors: # Checks boolean flag for survivors inside cell
                        self._goal_loc = (loc.x, loc.y) # Passes integers into my own personal location tuple
                        self._agent.log("Found a survivor!")
                        break
        
        if not self._goal_loc:
            self._agent.log("Could not find any survivors!") # If there are no survivors in the grid, print to console
            return [] # There are no coordinates to a non-existent survivor

        goal_loc_obj = create_location(self._goal_loc[0], self._goal_loc[1]) # Where the survivor is located
        '''
        # Priority queue: (priority, tie_breaker, location)
        to_visit = [] # Priority queue keeping track of locations, with built-in tie breaker implementation
        heapq.heappush(to_visit, (0, 0, start_loc)) # Has priority, tie breaker for same priorities, and the location
        visited: Dict[Location, Location] = {} # Dictionary tracking locations and how they were reached
        track_costs: Dict[Location, int] = {} # Keeps track of costs to reach every cell every time a_star_search() is called
        visited[start_loc] = None # We started at the starting location, we didn't get there from anywhere
        track_costs[start_loc] = 0 # Cost to reach the starting position is zero
        tie_breaker = 1 # This value will be incremented iff two values are given the same priority

        while to_visit: # This is done so long as the to_visit list is not empty
            _, _, current_loc = heapq.heappop(to_visit) # Get the highest priority location from to_visit

            if current_loc == self._goal_loc: # Ends function call is the survivor cell is reached
                return self.reconstruct_path(visited, start_loc, current_loc) # Returns calculated path to survivor

            for direction in Direction: # Observes all adjacent cells from current cell
                if direction == Direction.CENTER: # Skips current cell obsesrvation
                    continue

                neighbor_loc = current_loc.add(direction) # Gets location of adjacent cell
                
                if not self.is_valid_move(world, neighbor_loc): # Can't be a killer, fire, or high cost cell
                    continue

                # Calculate new cost
                new_move_cost = world.get_cell_at(neighbor_loc).move_cost # Cost of neighbour cell
                new_cost = track_costs[current_loc] + new_move_cost # Overrall cost to reach neighbour cell

                if (neighbor_loc not in track_costs or new_cost < track_costs[neighbor_loc]): # Logic to add a possible path-intermediate
                    track_costs[neighbor_loc] = new_cost # Reassigns cost of cell
                    cheb_heuristic = max(goal_loc_obj.y - neighbor_loc.y, goal_loc_obj.x - neighbor_loc.x) # Generates heuristic based on Chebychev distance between survivor location and neighbour location
                    priority = new_cost + cheb_heuristic # Priority of cell based on overall cost to reach and heuristic
                    heapq.heappush(to_visit, (priority, tie_breaker, neighbor_loc)) # Push new location to the priority queue
                    tie_breaker += 1 # Every location added is numbered, so if two equal priority locations occur, there's not gonna be a tussle over who gets popped
                    visited[neighbor_loc] = current_loc # Neighbour is reachable from the current location

        return []  # No path found

    def is_valid_move(self, world, location) -> bool:
        if not world.on_map(location): # Check if location is on the grid
            return False
            
        cell = world.get_cell_at(location) # CHeck if there is a cell at the location
        if not cell:
            return False 
            
        return not cell.is_killer_cell() and not cell.is_fire_cell() and cell.move_cost < self._agent.get_energy_level() # CHecks for dangerous or high cost cells and avoids them

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

    def send_and_end_turn(self, command: AgentCommand):
        """Send a command and end your turn."""
        self._agent.log(f"SENDING {command}")
        self._agent.send(command)
        self._agent.send(END_TURN())
    '''
    @override
    def think(self) -> None:
        self._agent.log("Thinking")

        # Examples of how to send a message to other agents.

        # Using AgentIDList() will send the message to all agents in your group
        # Useful for broadcasting information, such as about the world state (e.g. to tell people a survivor was saved) or needing help with a task (e.g. need another agent to help dig this rubble)).
        self._agent.send(SEND_MESSAGE(AgentIDList(), f"Hello from agent {self._agent.get_agent_id().id}!"))
        self._agent.send(SEND_MESSAGE(AgentIDList(), f"LOCATION {self._agent.get_location().x} {self._agent.get_location().y} : {self._agent.get_agent_id().id}"))

        # Putting in a specific agent ID will send to that agent only (e.g. sending information to a group leader).
        # Here we are telling agent 2 to move to our current location if we are the leader (ID = 1)

        if self._agent.get_agent_id().id == 1:
            message = f"MOVE {self._agent.get_location().x} {self._agent.get_location().y}"
            self._agent.send(SEND_MESSAGE(AgentIDList([AgentID(2, 1)]), message))

        # Retrieve the current state of the world.
        world = self.get_world()
        if world is None:
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return
        
        if self._agent.get_round_number() == 1:
            for row in world.get_world_grid():
                for rowCell in row:
                # Check if the top layer of the cell is a Survivor
                    if rowCell.has_survivors:
                        self._goal_locations.append(rowCell.location)
                    elif rowCell.is_fire_cell or rowCell.is_killer_cell:
                        self._danger_locations.add(rowCell.location)
                    elif rowCell.is_charging_cell:
                        self._medpack_locations.add(rowCell.location)

        # Fetch the cell at the agent’s current location. If the location is outside the world’s bounds,
        # return a default move action and end the turn.
        current_cell = world.get_cell_at(self._agent.get_location())
        if current_cell is None:
            self.send_and_end_turn(MOVE(Direction.CENTER))
            return

        # Get the top layer at the agent’s current location.
        top_layer = current_cell.get_top_layer()

        # If a survivor is present, save it and end the turn.
        if isinstance(top_layer, Survivor):
            self.send_and_end_turn(SAVE_SURV())
            # return is used after EVERY send_and_end_turn method call to "end turn early". This is so only 1 command is sent to aegis, meaning only 1 command is processed.
            # If 2+ commands are sent, only the last will be processed, leading to potentially unexpected behaviour from your agent(s).
            return

        # If rubble is present, try to clear it and end the turn.
        if isinstance(top_layer, Rubble):
            self.send_and_end_turn(TEAM_DIG())
            return
        
        # If the agent is on a charging cell, send a sleep command to recharge and end the turn.
        if current_cell.is_charging_cell():
            self._agent.send(SLEEP())

        # Additional logic can be added here (or anywhere), such as choosing which direction to move to based on lots of different factors!
        # You can make decisions using data you have learned through messages and stored in your data structures above
        # e.g. if you are the leader, you can find the closest agent to a survivor and tell that agent to go save them
        # A STAR STARTS HERE!!!!!!!!!!
        visited = {} # dictionary to keep track of visited vertices. keys are the cell locations, values are booleans
        for row in world.get_world_grid(): # iterating through the world grid. initially none of the vertices are visited, so all are set to False
            for rowCell in row:
                visited[rowCell.location] = False
        heuristic = 0 # initial heuristic value is 0

        #the only vertex we start with is the initial location
        to_visit = []
        # push the initial location into the todo list with a priority of the heuristic as the agent location and goal location, and the path as a list containing the initial location
        heapq.heappush(to_visit, (self.computingHeuristic(self._goal_locations[0], self._agent.get_location()),[self._agent.get_location()]))

        while len(to_visit) > 0: # planning the path/searching for best path
            x = heapq.heappop(to_visit) #first thing, pull the first element from todo list. the priority and element
            current_moveCost = x[0] - heuristic # the first element is the priority number, which is the move cost - heuristic value
            current_path = list(x[1]) # the second element is the path, which is a list of cell locations
            current_vertex = current_path[-1] # the last element in the path is the current vertex

            # if already visited, skip to the next vertex
            if visited[current_vertex]:
                continue
            
            visited[current_vertex] = True # mark the current vertex as visited

            # stop when found
            if (current_vertex == self._goal_locations[0]):
                print(f"Found the goal! Path is {current_path}!")
                self.send_and_end_turn(MOVE(current_path[0].direction_to(current_path[1])))
            
            # Default action: Move agent onto the adjacent cell with the lowest move cost + heuristic value
            for direction in Direction: # iterating through the neighbours of the current vertex
                if direction == Direction.CENTER: # skips over checking the center direction
                    continue

                adjacent_cell = world.get_cell_at(create_location(current_vertex.x, current_vertex.y).add(direction)) # getting the adjacent cell's adjacent cells
                
                if adjacent_cell is not None and not (adjacent_cell.is_fire_cell() or adjacent_cell.is_killer_cell()): # agent will not kill itself
                    heuristic = self.computingHeuristic(self._goal_locations[0], adjacent_cell.location) # computing the heuristic value for the adjacent cell

                    # if the adjacent cell is not visited, push it into the todo list
                    if visited[adjacent_cell.location] == False:
                        heapq.heappush(to_visit, (current_moveCost + adjacent_cell.move_cost + heuristic, current_path[:] + [adjacent_cell.location]))

        # Default action: Move the agent north if no other specific conditions are met. (you probably never want your code to reach here)
        self.send_and_end_turn(MOVE(Direction.CENTER))

    def send_and_end_turn(self, command: AgentCommand):
        """Send a command and end your turn."""
        self._agent.log(f"SENDING {command}")
        self._agent.send(command)
        self._agent.send(END_TURN())
    # My helper function!
    # This function computes the heuristic values for the A* search.
    def computingHeuristic(self, goal, locationExploring): 
        return max(goal.y - locationExploring.y, goal.x - locationExploring.x)
    '''