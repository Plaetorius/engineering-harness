"""Session verification is provided by the host at startup."""
_verifier = None


def configure_verifier(verifier):
    global _verifier
    _verifier = verifier


def verify_session(token):
    if _verifier is None:
        return None
    return _verifier(token)
