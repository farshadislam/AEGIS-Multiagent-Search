from typing import List, Set
from aegis import Location

survivors_locs: List[Location] = []
danger_zones: Set[Location] = set()
heal_locs: Set[Location] = set()

def add_survivor(loc: Location) -> None:
    survivors_locs.append(loc)

def add_danger(loc: Location) -> None:
    danger_zones.add(loc)

def add_heal(loc: Location) -> None:
    heal_locs.add(loc)

