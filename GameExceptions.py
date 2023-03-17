class ItemHeldException(Exception):
    def __init__(self, item):
        super(ItemHeldException, self).__init__(f"You are already holding {item}")


class ItemNotFoundException(Exception):
    def __init__(self, item):
        super(ItemNotFoundException, self).__init__(f"Cannot find f{item}")
