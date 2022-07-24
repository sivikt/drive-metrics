import time


def time_units():
    return {
        'sec': lambda elapsed_frac_sec: round(elapsed_frac_sec, 3)
    }


def create_elapsed_timer(time_unit: str):
    tic = time.perf_counter()

    def elapsed(message):
        print("%s [%f %s]" % (message, time_units().get(time_unit)(time.perf_counter() - tic), time_unit))

    return elapsed


def create_elapsed_timer_str(time_unit):
    tic = time.perf_counter()

    def elapsed() -> str:
        return '%f %s' % (time_units().get(time_unit)(time.perf_counter() - tic), time_unit)

    return elapsed
