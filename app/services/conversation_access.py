from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models import Conversation

async def validate_conversation_access(
    conversation_id: int,
    user_id: int
) -> bool:
    print(f"Validating access for user {user_id} to conversation {conversation_id}")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            return False

        return user_id in (
            conversation.jobseeker_id,
            conversation.recruiter_id,
        )
