class UserVisibleError(Exception):
    """Pipeline error whose message is safe to display directly to the user.

    Raise this instead of ValueError when the message is a German-language
    user instruction (e.g. "Kein Lebenslauf hinterlegt...").  The SSE error
    handler passes the message through; all other exceptions get a generic
    fallback string.
    """
