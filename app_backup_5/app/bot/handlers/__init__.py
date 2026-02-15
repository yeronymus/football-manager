from aiogram import Router
from .common import router as common_router
from .registration import router as registration_router
from .profile import router as profile_router
from .admin import router as admin_router

router = Router()
router.include_router(common_router)
router.include_router(registration_router)
router.include_router(profile_router)
router.include_router(admin_router)
