class StatusError(Exception):

    def __init__(self, status_code):
        self.status_code = status_code

    def __str__(self):
        return repr(self.status_code)
