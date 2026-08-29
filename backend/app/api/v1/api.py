from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, content, exercises, progress, ai, reading, writing,
    listening, speaking, personalization, vocabulary, payments, admin,
    ai_reading, personal_trainer, mobile, speech, lessons, practice_content, plan,
    attestation
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(vocabulary.router, prefix="/vocabulary", tags=["vocabulary"])
api_router.include_router(exercises.router, prefix="/exercises", tags=["exercises"])
api_router.include_router(practice_content.router, prefix="/practice-content", tags=["practice-content"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai-services"])
api_router.include_router(ai_reading.router, prefix="/ai/reading", tags=["ai-reading-generation"])
api_router.include_router(plan.router, prefix="/plan", tags=["study-plan"])
api_router.include_router(attestation.router, prefix="/attestation", tags=["attestation"])
api_router.include_router(reading.router, prefix="/reading", tags=["reading"])
api_router.include_router(writing.router, prefix="/writing", tags=["writing"])
api_router.include_router(listening.router, prefix="/listening", tags=["listening"])
api_router.include_router(speaking.router, prefix="/speaking", tags=["speaking"])
api_router.include_router(speech.router, prefix="/speech", tags=["speech"])
api_router.include_router(personalization.router, prefix="/personalization", tags=["personalization"])
api_router.include_router(personal_trainer.router, prefix="/personal-trainer", tags=["personal-trainer"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(mobile.router, prefix="/mobile", tags=["mobile"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"]) 