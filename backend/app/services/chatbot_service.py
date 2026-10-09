from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from openai import AsyncOpenAI
import traceback

from app.core.config import settings
from app.models.chat import ConversationModel, MessageModel
from app.schemas.chatbot import ChatResponse, ChatMessageResponse

class ChatbotService:
    @staticmethod
    def get_openai_client(use_litellm: bool = False) -> AsyncOpenAI:
        if not use_litellm and settings.OPENAI_API_KEY:
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
        elif settings.LLM_API_KEY:
            return AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                max_retries=1
            )
        elif settings.OPENAI_API_KEY:
            return AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0)
        else:
            raise ValueError("Neither OPENAI_API_KEY nor LLM_API_KEY is configured")

    @staticmethod
    def get_model(use_litellm: bool = False) -> str:
        if not use_litellm and settings.OPENAI_API_KEY:
            return settings.OPENAI_DEFAULT_MODEL
        return settings.LLM_MODEL

    @staticmethod
    async def process_chat(db: AsyncSession, conversation_id: Optional[str], message_content: str) -> ChatResponse:
        # 1. Find or create conversation
        if conversation_id:
            result = await db.execute(select(ConversationModel).where(ConversationModel.id == conversation_id))
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = ConversationModel(title=message_content[:50] + "...")
            db.add(conversation)
            await db.flush() # get ID

        # 2. Save user message
        user_msg = MessageModel(
            conversation_id=conversation.id,
            role="user",
            content=message_content
        )
        db.add(user_msg)
        await db.flush()

        # 3. Load conversation history
        messages_query = await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation.id)
            .order_by(MessageModel.created_at)
        )
        db_messages = messages_query.scalars().all()

        # Build messages for LLM
        messages_for_llm = [
            {"role": msg.role, "content": msg.content} 
            for msg in db_messages
        ]

        # 4. Call OpenAI API (with fallback to LiteLLM if needed)
        try:
            client = ChatbotService.get_openai_client(use_litellm=False)
            model = ChatbotService.get_model(use_litellm=False)
            response = await client.chat.completions.create(
                model=model,
                messages=messages_for_llm,
                max_tokens=2000
            )
            assistant_content = response.choices[0].message.content or ""
        except Exception as primary_err:
            if settings.LLM_API_KEY:
                print(f"Primary OpenAI call failed ({primary_err}), falling back to LiteLLM...")
                try:
                    client = ChatbotService.get_openai_client(use_litellm=True)
                    model = ChatbotService.get_model(use_litellm=True)
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages_for_llm,
                        max_tokens=2000
                    )
                    assistant_content = response.choices[0].message.content or ""
                except Exception as fallback_err:
                    print(f"Fallback LiteLLM Error: {fallback_err}")
                    raise RuntimeError(f"Error calling LLM: {str(fallback_err)}")
            else:
                print(f"OpenAI Chat Error: {primary_err}")
                raise RuntimeError(f"Error calling LLM: {str(primary_err)}")

        # 5. Save assistant message
        assistant_msg = MessageModel(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        return ChatResponse(
            conversation_id=conversation.id,
            message=ChatMessageResponse.model_validate(assistant_msg)
        )
