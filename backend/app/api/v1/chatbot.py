from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.core.db import get_db
from app.models.chat import ConversationModel, MessageModel
from app.schemas.chatbot import ChatRequest, ChatResponse, ConversationResponse, ConversationDetailResponse, ChatMessageResponse
from app.services.chatbot_service import ChatbotService

router = APIRouter(prefix="/chat", tags=["Chatbot OpenAI"])

@router.post("", response_model=ChatResponse)
async def chat_with_llm(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await ChatbotService.process_chat(db, payload.conversation_id, payload.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConversationModel).order_by(ConversationModel.updated_at.desc()))
    conversations = result.scalars().all()
    return [ConversationResponse.model_validate(c) for c in conversations]

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConversationModel).where(ConversationModel.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    msg_result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation.id)
        .order_by(MessageModel.created_at)
    )
    messages = msg_result.scalars().all()
    
    resp = ConversationDetailResponse.model_validate(conversation)
    resp.messages = [ChatMessageResponse.model_validate(m) for m in messages]
    return resp

@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConversationModel).where(ConversationModel.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    await db.delete(conversation)
    await db.commit()
    return None
