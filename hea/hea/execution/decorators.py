def cpu_bound(cls):
    cls._cpu_bound = True
    return cls


def io_bound(cls):
    cls._cpu_bound = False
    return cls


def is_cpu_bound(operator_class) -> bool:
    return getattr(operator_class, "_cpu_bound", False)
