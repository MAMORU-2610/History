
"""
sample_IDM--010104106b12e41d
"""


class IdmManager:
    __sample_idm = '010104106b12e41d'

    def __init__(self):
        self.old = None
        self.current = None

    def set_current(self, current):
        self.old = self.current
        self.current = current

    def check(self) -> bool:
        """
        oldとcurrentが等しいか否かを返す
        :return:
        """
        return self.old != self.current

    def current_is_sample(self) -> bool:
        """
        currentがサンプルのIDMと一致しているか否かを返す
        :return:
        """
        return self.current == IdmManager.__sample_idm
