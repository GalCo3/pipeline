from hermes.connections import SiteResponse


def site_error(
    local_response: SiteResponse, remote_response: SiteResponse | None, message: str
) -> None:
    if not local_response.is_success:
        error = local_response.error
    elif remote_response and not remote_response.is_success:
        error = remote_response.error
    else:
        return

    cause = error if isinstance(error, BaseException) else None
    raise RuntimeError(message) from cause
