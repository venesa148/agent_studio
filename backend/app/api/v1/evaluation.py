from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.core.security import verify_api_key
from app.schemas.evaluation import EvaluationCreate, EvaluationResponse, EvaluationUpdate
from app.models.evaluation import EvaluationModel
from app.services.evaluator_service import EvaluatorService
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

@router.post("/seed-defaults", response_model=List[EvaluationResponse])
async def seed_default_test_cases(db: AsyncSession = Depends(get_db)):
    """Menyediakan dataset 5 test case standar BPJS Care jika tabel evaluasi masih kosong."""
    existing_res = await db.execute(select(EvaluationModel))
    existing = existing_res.scalars().all()
    if existing:
        return existing

    defaults = [
        {
            "agent": "Asisten BPJS Care",
            "input": "Dada saya sakit seperti tertekan dan sesak napas berat sejak 30 menit lalu!",
            "expected": "classify_complaint (Emergency / Rujuk IGD)",
        },
        {
            "agent": "Asisten BPJS Care",
            "input": "Tolong periksa apakah kartu BPJS saya 0001234567890 masih aktif?",
            "expected": "check_bpjs (Status Aktif)",
        },
        {
            "agent": "Asisten BPJS Care",
            "input": "Saya punya surat rujukan faskes 1 nomor RUJ-9999, tolong cek statusnya.",
            "expected": "get_referral_status (Verifikasi Rujukan)",
        },
        {
            "agent": "Asisten BPJS Care",
            "input": "Saya ingin berobat ke dokter spesialis penyakit dalam di RSUD Tarakan Jakarta.",
            "expected": "search_hospital, find_specialist",
        },
        {
            "agent": "Asisten BPJS Care",
            "input": "Saya setuju daftar ke RSUD Tarakan tanggal 15 Oktober 2026 jam 08.00 WIB.",
            "expected": "create_appointment (Booking Antrean)",
        },
    ]

    created = []
    for d in defaults:
        item = EvaluationModel(**d)
        db.add(item)
        created.append(item)

    await db.commit()
    for item in created:
        await db.refresh(item)
    return created

@router.post("/{eval_id}/run", response_model=EvaluationResponse)
async def run_evaluation_item(eval_id: str, db: AsyncSession = Depends(get_db)):
    """
    Menjalankan 1 test case: Mini Agent dieksekusi, lalu Evaluator Agent (LLM Judge)
    menilai hasilnya berdasarkan 5 metrik baku.
    """
    result = await EvaluatorService.run_single_evaluation(db, eval_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test case evaluasi tidak ditemukan.")
    return result

@router.post("/run-all", response_model=List[EvaluationResponse])
async def run_all_evaluation_items(db: AsyncSession = Depends(get_db)):
    """Menjalankan seluruh test case evaluasi secara otomatis menggunakan LLM as a Judge."""
    return await EvaluatorService.run_all_evaluations(db)

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
