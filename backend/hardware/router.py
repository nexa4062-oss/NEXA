from fastapi import APIRouter, Depends
from auth.service import get_current_user
from models.orm import User
from hardware.detector import HardwareDetector

router = APIRouter()
detector = HardwareDetector()


@router.get("/")
async def get_hardware_info(current_user: User = Depends(get_current_user)):
    return await detector.detect_all()


@router.get("/gpu")
async def get_gpu_info(current_user: User = Depends(get_current_user)):
    return await detector.detect_gpu()


@router.get("/compatibility")
async def check_model_compatibility(current_user: User = Depends(get_current_user)):
    hw = await detector.detect_all()
    return detector.assess_model_compatibility(hw)
