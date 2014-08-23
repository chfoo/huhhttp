from huhhttp.fusil.tools import minmax


class AutoMangle(object):
    def __init__(self, config):
        self.hard_max_op = 10000
        self.hard_min_op = 0
        self.aggressivity = 0.1
        self.fixed_size_factor = 1.0
        self.config = config

    def setupConf(self, data):
        operations = ["bit"]
        size_factor = 0.30

        if 0.25 <= self.aggressivity:
            operations.append("increment")
        if 0.30 <= self.aggressivity:
            operations.extend(("replace", "special_value"))
        if 0.50 <= self.aggressivity:
            operations.extend(("insert_bytes", "delete_bytes"))
            size_factor = 0.20
        self.config.operations = operations

        count = len(data) * size_factor * self.fixed_size_factor
        count = minmax(self.hard_min_op, count, self.hard_max_op)
        count = int(count * self.aggressivity)
        self.config.max_op = max(count, self.hard_min_op)
        self.config.min_op = max(int(self.config.max_op * 0.80), self.hard_min_op)

