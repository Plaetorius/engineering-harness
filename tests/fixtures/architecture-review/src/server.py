from .identity import verify_session
from .store import find_document


def get_document(token, document_id):
    session = verify_session(token)
    if session is None:
        return {'status': 401}
    document = find_document(document_id)
    if document is None:
        return {'status': 404}
    return {'status': 200, 'body': document['body']}


ROUTES = {'GET /documents/:id': get_document}
