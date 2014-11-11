import time


def RateLimited(maxPerSecond):
    minInterval = 1.0 / float(maxPerSecond)

    def decorate(func):
        lastTimeCalled = [0.0]

        def rateLimitedFunction(*args, **kargs):
            elapsed = time.clock() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait > 0:
                time.sleep(leftToWait)
            ret = func(*args, **kargs)
            lastTimeCalled[0] = time.clock()
            return ret
        return rateLimitedFunction
    return decorate


def rating_filter(rating):
    if rating > 10:
        return int(rating)
    return rating


class StatusError(Exception):

    def __init__(self, status_code):
        self.status_code = status_code

    def __str__(self):
        return repr(self.status_code)
