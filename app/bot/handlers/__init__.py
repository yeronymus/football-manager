from aiogram import Router
from .common import router as common_router
from .registration import router as registration_router
from .profile import router as profile_router
from .admin import router as admin_router
from .admin_handlers import router as admin_handlers_router
from .admin_system import router as admin_system_router
from .game_handlers import router as game_handlers_router
from .setup_handlers import router as setup_handlers_router
from .stats_handlers import router as stats_handlers_router
from .vote_handlers import router as vote_handlers_router

router = Router()
router.include_router(common_router)
router.include_router(registration_router)
router.include_router(profile_router)
router.include_router(admin_router)
router.include_router(admin_handlers_router)
router.include_router(admin_system_router)
router.include_router(game_handlers_router)
router.include_router(setup_handlers_router)
router.include_router(stats_handlers_router)
router.include_router(vote_handlers_router)
