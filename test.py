class IdmManager:

    def __init__(self):
        self.old = 1
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
    print(idm_m.old)
    idm_m.old = idm_m.old + 2
    print(idm_m.old)
    # if idm_m.check():
    #     print('aaa')


if __name__ == '__main__':
    test_func()
