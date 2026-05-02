from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SpeechEvaluateResponseTranscriptWord(BaseModel):
    word: str
    startMs: Optional[int] = None
    endMs: Optional[int] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class SpeechEvaluateResponseTranscript(BaseModel):
    text: str
    words: Optional[List[SpeechEvaluateResponseTranscriptWord]] = None


class SpeechEvaluateResponseAccuracy(BaseModel):
    wer: float = Field(..., ge=0.0)
    correct: int
    insertions: int
    deletions: int
    substitutions: int


class SpeechEvaluateResponsePronunciationIssue(BaseModel):
    word: str
    issue: str
    suggestion: Optional[str] = None


class SpeechEvaluateResponsePronunciation(BaseModel):
    issues: List[SpeechEvaluateResponsePronunciationIssue] = []


class SpeechEvaluateResponseFluencyPause(BaseModel):
    start: int
    end: int


class SpeechEvaluateResponseFluency(BaseModel):
    wpm: float
    avgPauseMs: Optional[float] = None
    longPauses: List[SpeechEvaluateResponseFluencyPause] = []


class SpeechEvaluateResponseTiming(BaseModel):
    durationMs: int


class SpeechEvaluateResponse(BaseModel):
    overallScore: float = Field(..., ge=0.0, le=100.0)
    accuracy: SpeechEvaluateResponseAccuracy
    pronunciation: SpeechEvaluateResponsePronunciation
    fluency: SpeechEvaluateResponseFluency
    timing: SpeechEvaluateResponseTiming
    transcript: SpeechEvaluateResponseTranscript
    tips: List[str] = []


# Request uses multipart form in FastAPI route, so we only define helper model
class SpeechEvaluateRequestMeta(BaseModel):
    reference_text: str
    language: str = Field("en-US")



