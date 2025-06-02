from typing import override # Test message

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
)
from mas.agent import BaseAgent, Brain, AgentController

from typing import override

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
        self._agent_locations: list[Location | None] = [None] * self.NUM_AGENTS
        self._current_goal: Location | None = None

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
        elif msg_list[0] == "LOCATION":
            # Extract the agent ID and its location from the message
            agent_id = int(msg_list[1]) 
            location_x = int(msg_list[2])
            location_y = int(msg_list[3])
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

        else:
            # A message was sent that doesn't match any of our known formats
            self._agent.log(f"Unknown message format: {smr.msg}")

    @override
    def think(self) -> None:
        self._agent.log("Thinking")

        # Examples of how to send a message to other agents.

        # Using AgentIDList() will send the message to all agents in your group
        # Useful for broadcasting information, such as about the world state (e.g. to tell people a survivor was saved) or needing help with a task (e.g. need another agent to help dig this rubble)).
        self._agent.send(SEND_MESSAGE(AgentIDList(), f"Hello from agent {self._agent.get_agent_id().id}!"))
        self._agent.send(SEND_MESSAGE(AgentIDList(), f"LOCATION {self._agent.get_agent_id().id} {self._agent.get_location().x} {self._agent.get_location().y}"))

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
        
        goalLocation = []
        # Iterate through all cells in the world
        for row in world.get_world_grid():
            for rowCell in row:
                # Check if the top layer of the cell is a Survivor
                if rowCell.has_survivors:
                    goalLocation.append(rowCell.location)

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


        # Additional logic can be added here (or anywhere), such as choosing which direction to move to based on lots of different factors!
        # You can make decisions using data you have learned through messages and stored in your data structures above
        # e.g. if you are the leader, you can find the closest agent to a survivor and tell that agent to go save them
        #A STAR STARTS HERE!!!!!!!!!!
        visited = {} # dictionary to keep track of visited vertices. keys are the cell locations, values are booleans
        for row in world.get_world_grid(): # iterating through the world grid. initially none of the vertices are visited, so all are set to False
            for rowCell in row:
                visited[rowCell.location] = False
        heuristic = 0 # initial heuristic value is 0

        #the only vertex we start with is the initial location
        to_visit = []
        # push the initial location into the todo list with a priority of the heuristic as the agent location and goal location, and the path as a list containing the initial location
        heapq.heappush(to_visit, (self.computingHeuristic(goalLocation[0], self._agent.get_location()),[self._agent.get_location()]))

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
            if (current_vertex == goalLocation[0]):
                print(f"Found the goal! Path is {current_path}!")
                self.send_and_end_turn(MOVE(current_path[0].direction_to(current_path[1])))
            
            # Default action: Move agent onto the adjacent cell with the lowest move cost + heuristic value
            for direction in Direction: # iterating through the neighbours of the current vertex
                if direction == Direction.CENTER: # skips over checking the center direction
                    continue

                adjacent_cell = world.get_cell_at(create_location(current_vertex.x, current_vertex.y).add(direction)) # getting the adjacent cell's adjacent cells
                
                if adjacent_cell is not None and not (adjacent_cell.is_fire_cell() or adjacent_cell.is_killer_cell()): # agent will not kill itself
                    heuristic = self.computingHeuristic(goalLocation[0], adjacent_cell.location) # computing the heuristic value for the adjacent cell

                    # if the adjacent cell is not visited, push it into the todo list
                    if visited[adjacent_cell.location] == False:
                        heapq.heappush(to_visit, (current_moveCost + adjacent_cell.move_cost + heuristic, current_path[:] + [adjacent_cell.location]))

        # Default action: Move the agent north if no other specific conditions are met. (you probably never want your code to reach here)
        self.send_and_end_turn(MOVE(Direction.NORTH))

    def send_and_end_turn(self, command: AgentCommand):
        """Send a command and end your turn."""
        self._agent.log(f"SENDING {command}")
        self._agent.send(command)
        self._agent.send(END_TURN())
    # My helper function!
    # This function computes the heuristic values for the A* search.
    def computingHeuristic(self, goal, locationExploring):#adjacentDirection): 
        heuristic = 0 #initial heuristic value is 0 

        if locationExploring.x == goal.x:
            heuristic = abs(locationExploring.y - goal.y) # if the x coordinates are the same, the heuristic is the difference in y coordinates
        elif locationExploring.y == goal.y:
            heuristic = abs(locationExploring.x - goal.x) # if the y coordinates are the same, the heuristic is the difference in x coordinates
        else:
            heuristic =  abs(locationExploring.y - goal.y)/abs(locationExploring.x - goal.x)  # if the x and y coordinates are different, the heuristic is the slope formula
        return heuristic