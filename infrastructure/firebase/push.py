from infrastructure.firebase.client import send_push
from infrastructure.firebase.tokens import get_user_tokens

def send_reminder(user_id: str, title: str, body: str, reminder_id: str):
    tokens = get_user_tokens(user_id)
    for token in tokens:
        send_push(
            token=token,
            title=title,
            body=body,
            data={"reminder_id": reminder_id}
        )
