from uuid import UUID, uuid5


def auth_subject_to_user_id(subject: str) -> UUID:
    try:
        return UUID(subject)
    except ValueError:
        namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
        return uuid5(namespace, subject)
