def get_preferred_mimetype(accept: str, supported_mimetypes: list[str]) -> str | None:
    """
    Gets which mimetype the user agent prefers

    Args:
        accept: the `Accept` header from the user agent.
        supported_mimetypes: which mimetypes the server supports and can serve a response for.
    Returns:
        The mimetype that was selected, if supported.
            
    """
    alternatives = accept.split(",")
    for alternative in alternatives:
        # We ignore options here as we don't support it.
        # Thankfully browsers are nice enough to give the mimetypes in order of how much they prefer them anyways.
        parts = alternative.split(";")
        mimetype = parts[0].lower()
        assert mimetype is not None, "mimetype cannot be None as when splitting we always get at least one item"

        if mimetype in supported_mimetypes:
            return mimetype
