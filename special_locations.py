from typing import Dict, Set
from aegis import Location

survivors_locs: Dict[Location : int] = {}
danger_zones: Set[Location] = set()
heal_locs: Set[Location] = set()

def add_survivor(loc: Location, gid: int) -> None:
    survivors_locs[loc] = gid

def add_danger(loc: Location) -> None:
    danger_zones.add(loc)

def add_heal(loc: Location) -> None:
    heal_locs.add(loc)

