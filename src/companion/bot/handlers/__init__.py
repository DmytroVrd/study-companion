from aiogram import Router

from companion.bot.handlers import audio, context, export, quiz, start, stats, study, upload


def build_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(context.router)
    router.include_router(upload.router)
    router.include_router(export.router)
    router.include_router(quiz.router)
    router.include_router(stats.router)
    router.include_router(study.router)
    router.include_router(audio.router)
    return router
