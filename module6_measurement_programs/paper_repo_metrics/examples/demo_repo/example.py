"""Small fixture. Docstrings are literals under the documented line policy."""

class Counter:
    def __init__(self):
        self.value = 0

    def get_value(self):
        return self.value

    def set_value(self, value: int):
        if value >= 0 and value < 100:
            self.value = value
        else:
            self.value = 0
        return self.get_value()


def sum_positive(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
    return total
