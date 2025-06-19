def serialize_message(message):
    return {
        "id": message.id,
        "date": message.date.isoformat(),
        "mentioned": message.mentioned,
        "scheduled": message.scheduled,
        "from_scheduled": message.from_scheduled,
        "has_protected_content": message.has_protected_content,
        "text": message.text,
        "outgoing": message.outgoing,
        "chat": (
            {
                "id": message.chat.id,
                "type": str(message.chat.type),
                "title": message.chat.title,
                "username": message.chat.username,
            }
            if message.chat
            else None
        ),
        "from_user": (
            {
                "id": message.from_user.id,
                "first_name": message.from_user.first_name,
                "last_name": message.from_user.last_name,
                "username": message.from_user.username,
                "is_bot": message.from_user.is_bot,
            }
            if message.from_user
            else None
        ),
    }
