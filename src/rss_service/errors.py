class RssServiceError(Exception):
    pass


class NotFoundError(RssServiceError):
    pass


class ConflictError(RssServiceError):
    pass


class ValidationError(RssServiceError):
    pass
