from logger import setup_logger, INFO
import datetime

log = setup_logger(__name__, INFO)

class Member:
    def __init__(self, name: str, ip: str, port: int):
        self.name = name
        self.ip = ip
        self.port = port
    
    def get_user(self):
        log.info(f"Getting user's info: {self.name} ({self.ip}:{self.port})")
        return f"{self.name} ({self.ip}:{self.port})"

class Channel:
    def __init__(self, channel_id: int, name: str, description: str, author: str):
        self.id = channel_id
        self.name = name
        self.description = description
        self.author = author
        self.members:list[Member] = []
        self.timestamp = datetime.datetime.now().timestamp()
        self.created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_member(self, name: str, ip: str, port: int) -> None|str:
        log.info(self.members)
        for member in self.members:
            log.info(member)
            if name == member.name:
                log.error(f"Member {name} already exists in the channel.")
                return "Member already exists"
        member = Member(name, ip, port)
        self.members.append(member)

    def remove_member(self, name: str):
        self.members = [member for member in self.members if member.name != name]
