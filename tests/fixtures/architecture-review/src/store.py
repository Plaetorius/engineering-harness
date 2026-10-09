"""Existing in-process document persistence abstraction."""
_documents = {1: {'owner_id': 'owner-a', 'body': 'Synthetic document'}}


def find_document(document_id):
    return _documents.get(document_id)
