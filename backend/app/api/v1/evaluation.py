from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.evaluation import EvaluationCreate, EvaluationResponse, EvaluationUpdate
from app.models.evaluation import EvaluationModel
import datetime

router = APIRouter(prefix="/evaluation", tags=["Evaluation"], dependencies=[Depends(verify_api_key)])

@router.get("", response_model=List[EvaluationResponse])
async def list_evaluations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationModel).order_by(EvaluationModel.created_at.desc()))
    return result.scalars().all()

@router.post("", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation(payload: EvaluationCreate, db: AsyncSession = Depends(get_db)):
    db_eval = EvaluationModel(**payload.model_dump())
    db.add(db_eval)
    await db.commit()
    await db.refresh(db_eval)
    return db_eval

@router.put("/{eval_id}", response_model=EvaluationResponse)
async def update_evaluation(eval_id: str, payload: EvaluationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationModel).where(EvaluationModel.id == eval_id))
    eval_model = result.scalar_one_or_none()
    if not eval_model:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(eval_model, key, value)
    
    await db.commit()
    await db.refresh(eval_model)
    return eval_model

@router.delete("/{eval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(eval_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationModel).where(EvaluationModel.id == eval_id))
    eval_model = result.scalar_one_or_none()
    if not eval_model:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    await db.delete(eval_model)
    await db.commit()
    return None
