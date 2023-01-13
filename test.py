class IdmManager:

    def __init__(self):
        self.old = None
        self.current = None

    def set_current(self, current):
        self.old = self.current
        self.current = current

    def check(self) -> bool:
        if self.old is None and self.current is None:
            return True

        return self.old != self.current


idm_m = IdmManager()


def test_func():
    if idm_m.check():
        print('aaa')


if __name__ == '__main__':
    test_func()
