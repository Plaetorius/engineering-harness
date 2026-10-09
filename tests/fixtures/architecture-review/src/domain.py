from .transport import format_response


def permission_denial():
    return format_response(403, 'Denied')
