from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.trace import TraceRunResponse, TraceStepResponse, SimulationCase
from app.models.trace import TraceLogModel

router = APIRouter(prefix="/agent", tags=["Trace & Simulations"], dependencies=[Depends(verify_api_key)])

@router.get("/trace/{run_id}", response_model=TraceRunResponse)
async def get_trace_log(run_id: str, db: AsyncSession = Depends(get_db)):
    """
    Mengambil detail timeline eksekusi trace log berdasarkan run_id.
    """
    result = await db.execute(
        select(TraceLogModel)
        .where(TraceLogModel.run_id == run_id)
        .order_by(TraceLogModel.step_no.asc())
    )
    logs = result.scalars().all()

    if not logs:
        raise HTTPException(
            status_code=404,
            detail=f"Trace log untuk run_id '{run_id}' tidak ditemukan dalam database."
        )

    steps = [
        TraceStepResponse(
            step_no=l.step_no,
            type=l.step_type,
            title=l.title,
            duration_ms=l.duration_ms,
            detail=l.detail,
            status=l.status
        )
        for l in logs
    ]
    tot_duration = sum(l.duration_ms for l in logs)

    return TraceRunResponse(
        run_id=run_id,
        status="OK",
        total_duration_ms=tot_duration,
        total_tokens=0,
        steps=steps
    )

from app.models.evaluation import EvaluationModel


@router.get("/simulations", response_model=List[SimulationCase])
async def list_simulations(db: AsyncSession = Depends(get_db)):
    """
    Mengambil daftar test cases skenario pengujian Agent secara dinamis dari database.
    """
    res = await db.execute(select(EvaluationModel).order_by(EvaluationModel.created_at.desc()))
    records = res.scalars().all()

    if not records:
        return []

    return [
        SimulationCase(
            id=str(r.id),
            scenario=r.agent or "Skenario Uji",
            input=r.input or "-",
            expected=r.expected or "-",
            actual=r.actual or "Belum diuji",
            status=r.status or "idle",
            duration=f"{r.details.get('duration_ms', 100)}ms" if isinstance(r.details, dict) and "duration_ms" in r.details else "100ms"
        )
        for r in records
    ]
