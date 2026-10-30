"""
Address helpers shared by several scripts.

The same store address can be written many ways:
    "1513 East 53rd Street, Suite 2"   vs   "1513 E 53RD ST 1ST"
To compare addresses we reduce each one to a short "key" with only the parts
that identify the building: house number, (direction), and first street word.
"""

import re

# Standard abbreviations so long and short spellings match.
ABBREVIATIONS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
                 "STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "BOULEVARD": "BLVD",
                 "DRIVE": "DR", "PARKWAY": "PKWY", "PLACE": "PL", "HIGHWAY": "HWY",
                 "COURT": "CT", "LANE": "LN"}
DIRECTIONS = {"N", "S", "E", "W"}


def address_key(address, keep_direction=True):
    """Reduce an address to 'house number [+ direction] + first word of street name'.

    '1513 East 53rd Street, Suite 2' -> '1513 E 53RD'   (keep_direction=True)
                                     -> '1513 53RD'     (keep_direction=False)

    Use keep_direction=False when one source sometimes leaves out "West", "North", etc.
    Returns None if the address doesn't start with a house number."""
    text = str(address).upper()
    text = re.sub(r"^(\d+)-\S+", r"\1", text)      # '4853-A N BROADWAY' -> '4853 N BROADWAY'
    text = re.sub(r"^(\d+)[A-Z]\b", r"\1", text)   # '172A W MADISON' -> '172 W MADISON'
    text = re.sub(r"\b\d+/\d+\b", " ", text)       # drop fractions like '1/2'
    words = [ABBREVIATIONS.get(w, w) for w in re.sub(r"[^A-Z0-9 ]", " ", text).split()]
    if not words or not words[0].isdigit():
        return None
    rest = words[1:]
    direction = [rest.pop(0)] if rest and rest[0] in DIRECTIONS else []
    if not rest:
        return None
    return " ".join([words[0]] + (direction if keep_direction else []) + rest[:1])
