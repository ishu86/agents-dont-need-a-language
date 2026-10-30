from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    name: str
    email: Optional[str]

def find(users: list[User], uid: int) -> Optional[User]:
    for u in users:
        if u.id == uid:
            return u
    return None

def total_age(ages: list[int]) -> int:
    return sum(ages)

def main() -> None:
    users = [User(1, "a", None), User(id=2, name="b")]          # 8 missing field
    u = find(users, "1")                                        # 1 wrong arg type
    print(u.name)                                               # 6 optional access
    print(users[0].nmae)                                        # 2 typo attribute
    x: int = total_age([1, 2], 3)                               # 5 wrong arg count
    print(undefined_var)                                        # 4 undefined
    y: str = total_age([1])                                     # 3 wrong return type use
    print(users[0].email.upper())                               # 6b optional access
