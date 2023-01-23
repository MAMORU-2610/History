class UserIdManager:
    def __init__(self, start_id=0):
        self.user_id = start_id

    def up_count(self):
        self.user_id += 1
