import enum


class Position(str, enum.Enum):
    GK = "GK"
    
    # Defenders
    DEF = "DEF" # General Defender
    LB = "LB"
    CB = "CB"
    RB = "RB"
    LWB = "LWB"
    RWB = "RWB"
    
    # Midfielders
    MID = "MID" # General Midfielder
    CDM = "CDM"
    CM = "CM"
    CAM = "CAM"
    LM = "LM"
    RM = "RM"
    
    # Forwards
    FWD = "FWD" # General Forward
    ST = "ST"
    LW = "LW"
    RW = "RW"
    CF = "CF"
    SUB = "SUB" # Substitute

    # Universal Event & Non-Football Roles (Trips, Book Clubs, Padel, Board Games)
    DRIVER = "DRIVER"
    PASSENGER = "PASSENGER"
    GUIDE = "GUIDE"
    SPEAKER = "SPEAKER"
    MEMBER = "MEMBER"
    HOST = "HOST"
    PLAYER = "PLAYER"
    PARTICIPANT = "PARTICIPANT"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UNIVERSAL = "UNIVERSAL"

class GameStatus(str, enum.Enum):
    OPEN = "open"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"

class GameType(str, enum.Enum):
    REGULAR = "regular"   # Regular match
    DRAFT = "draft"       # Draft match

class SignupStatus(str, enum.Enum):
    ACTIVE = "active"
    RESERVE = "reserve"
    CANCELLED = "cancelled"

class Team(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"

class Language(str, enum.Enum):
    en = "en"
    ru = "ru"
    cs = "cs"
    cz = "cz"

class InventoryCategory(str, enum.Enum):
    BIBS = "BIBS"
    BALLS = "BALLS"
    MEDICAL = "MEDICAL"
    EQUIPMENT = "EQUIPMENT"
    OTHER = "OTHER"

class InventoryStatus(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    REPLACE_SOON = "REPLACE_SOON"
    URGENT_PURCHASE = "URGENT_PURCHASE"

