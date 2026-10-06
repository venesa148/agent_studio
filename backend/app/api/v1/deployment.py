from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.deployment import DeploymentCreate, DeploymentResponse
from app.models.deployment import DeploymentModel

router = APIRouter(prefix="/deployments", tags=["Deployments"], dependencies=[Depends(verify_api_key)])

@router.get("", response_model=List[DeploymentResponse])
async def list_deployments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeploymentModel).order_by(DeploymentModel.deployedAt.desc()))
    return result.scalars().all()

@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(payload: DeploymentCreate, db: AsyncSession = Depends(get_db)):
    db_deployment = DeploymentModel(**payload.model_dump())
    db.add(db_deployment)
    await db.commit()
    await db.refresh(db_deployment)
    return db_deployment

@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeploymentModel).where(DeploymentModel.id == deployment_id))
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await db.delete(deployment)
    await db.commit()
    return None
