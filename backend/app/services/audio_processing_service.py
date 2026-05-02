import asyncio
import aiohttp
import aiofiles
import io
import base64
import tempfile
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
import json
import warnings
from datetime import datetime, timedelta

# Suppress pkg_resources deprecation warning from webrtcvad
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
    module="webrtcvad"
)

# Audio processing libraries
import speech_recognition as sr
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import librosa
import numpy as np
import webrtcvad
from scipy.io import wavfile

from app.core.config import settings
from app.core.cache import get_redis
from app.models.speaking import AudioFormat, AudioQuality

logger = logging.getLogger(__name__)

class AudioProcessingService:
    """
    Comprehensive audio processing service for speech recognition,
    format conversion, quality analysis, and preprocessing
    """
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.supported_formats = [
            AudioFormat.WAV, AudioFormat.MP3, AudioFormat.WEBM, 
            AudioFormat.OGG, AudioFormat.M4A, AudioFormat.FLAC
        ]
        self.target_sample_rate = 16000  # Standard for speech recognition
        self.target_channels = 1  # Mono for speech
        self.redis = None
        
    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def process_audio_for_speech_recognition(
        self, 
        audio_data: bytes, 
        source_format: str = "webm",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process audio data for optimal speech recognition
        
        Args:
            audio_data: Raw audio bytes
            source_format: Source audio format
            user_id: User ID for caching and personalization
            
        Returns:
            Dict containing processed audio data and metadata
        """
        try:
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=f".{source_format}", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Load audio with pydub
                if source_format.lower() == "webm":
                    audio = AudioSegment.from_file(temp_file_path, format="webm")
                else:
                    audio = AudioSegment.from_file(temp_file_path)

                # Get original metadata
                original_metadata = {
                    "duration_ms": len(audio),
                    "sample_rate": audio.frame_rate,
                    "channels": audio.channels,
                    "sample_width": audio.sample_width,
                    "format": source_format
                }

                # Convert to optimal format for speech recognition
                processed_audio = await self._optimize_for_speech_recognition(audio)
                
                # Analyze audio quality
                quality_analysis = await self._analyze_audio_quality(processed_audio)
                
                # Extract audio features
                features = await self._extract_audio_features(processed_audio)
                
                # Convert to bytes for API calls
                processed_bytes = await self._audio_to_bytes(processed_audio, format="wav")
                
                # Cache processed audio if user provided
                if user_id:
                    await self._cache_processed_audio(user_id, processed_bytes, quality_analysis)

                return {
                    "success": True,
                    "processed_audio": base64.b64encode(processed_bytes).decode('utf-8'),
                    "original_metadata": original_metadata,
                    "processed_metadata": {
                        "duration_ms": len(processed_audio),
                        "sample_rate": processed_audio.frame_rate,
                        "channels": processed_audio.channels,
                        "format": "wav"
                    },
                    "quality_analysis": quality_analysis,
                    "features": features,
                    "processing_time": datetime.utcnow().isoformat()
                }

            finally:
                # Cleanup temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "audio_processing_error"
            }

    async def speech_to_text(
        self, 
        audio_data: bytes, 
        language: str = "en-US",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Convert speech audio to text using multiple recognition engines
        
        Args:
            audio_data: Processed audio bytes (WAV format preferred)
            language: Target language for recognition
            user_id: User ID for personalization and caching
            
        Returns:
            Dict containing transcription results from multiple engines
        """
        try:
            # Check cache first
            if user_id:
                cache_key = f"stt:{user_id}:{hash(audio_data)}"
                redis = await self._get_redis()
                cached_result = await redis.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)

            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                results = {}
                
                # Google Speech Recognition (Primary)
                try:
                    with sr.AudioFile(temp_file_path) as source:
                        audio = self.recognizer.record(source)
                        
                    # Google Web Speech API (Free)
                    google_result = await asyncio.to_thread(
                        self.recognizer.recognize_google,
                        audio,
                        language=language,
                        show_all=True
                    )
                    
                    if google_result and 'alternative' in google_result:
                        alternatives = google_result['alternative']
                        results["google"] = {
                            "transcript": alternatives[0].get('transcript', ''),
                            "confidence": alternatives[0].get('confidence', 0.0),
                            "alternatives": [
                                {
                                    "transcript": alt.get('transcript', ''),
                                    "confidence": alt.get('confidence', 0.0)
                                }
                                for alt in alternatives[:3]  # Top 3 alternatives
                            ]
                        }
                    else:
                        results["google"] = {
                            "transcript": google_result if isinstance(google_result, str) else "",
                            "confidence": 0.8,  # Default confidence for string results
                            "alternatives": []
                        }
                        
                except sr.UnknownValueError:
                    results["google"] = {
                        "transcript": "",
                        "confidence": 0.0,
                        "error": "Could not understand audio"
                    }
                except sr.RequestError as e:
                    results["google"] = {
                        "transcript": "",
                        "confidence": 0.0,
                        "error": f"Google API error: {e}"
                    }

                # Whisper (OpenAI) - if available
                if hasattr(sr, 'recognize_whisper'):
                    try:
                        whisper_result = await asyncio.to_thread(
                            self.recognizer.recognize_whisper,
                            audio,
                            language=language[:2]  # Whisper uses 2-letter codes
                        )
                        results["whisper"] = {
                            "transcript": whisper_result,
                            "confidence": 0.9,  # Whisper generally high confidence
                            "alternatives": []
                        }
                    except Exception as e:
                        results["whisper"] = {
                            "transcript": "",
                            "confidence": 0.0,
                            "error": f"Whisper error: {e}"
                        }

                # Sphinx (Offline fallback)
                try:
                    sphinx_result = await asyncio.to_thread(
                        self.recognizer.recognize_sphinx,
                        audio
                    )
                    results["sphinx"] = {
                        "transcript": sphinx_result,
                        "confidence": 0.6,  # Sphinx generally lower confidence
                        "alternatives": []
                    }
                except Exception as e:
                    results["sphinx"] = {
                        "transcript": "",
                        "confidence": 0.0,
                        "error": f"Sphinx error: {e}"
                    }

                # Select best result
                best_result = self._select_best_transcription(results)
                
                final_result = {
                    "success": True,
                    "transcript": best_result["transcript"],
                    "confidence": best_result["confidence"],
                    "language": language,
                    "engine_used": best_result["engine"],
                    "all_results": results,
                    "processing_time": datetime.utcnow().isoformat()
                }

                # Cache result
                if user_id:
                    redis = await self._get_redis()
                    await redis.setex(
                        cache_key, 
                        timedelta(hours=1).total_seconds(),
                        json.dumps(final_result)
                    )

                return final_result

            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Speech-to-text error: {e}")
            return {
                "success": False,
                "transcript": "",
                "confidence": 0.0,
                "error": str(e),
                "error_type": "speech_recognition_error"
            }

    async def convert_audio_format(
        self, 
        audio_data: bytes, 
        source_format: str, 
        target_format: str = "wav",
        quality: AudioQuality = AudioQuality.MEDIUM
    ) -> Dict[str, Any]:
        """
        Convert audio between different formats with quality control
        
        Args:
            audio_data: Source audio bytes
            source_format: Source format (webm, mp3, wav, etc.)
            target_format: Target format
            quality: Conversion quality level
            
        Returns:
            Dict containing converted audio data and metadata
        """
        try:
            # Create temporary source file
            with tempfile.NamedTemporaryFile(suffix=f".{source_format}", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Load audio
                if source_format.lower() == "webm":
                    audio = AudioSegment.from_file(temp_file_path, format="webm")
                else:
                    audio = AudioSegment.from_file(temp_file_path)

                # Apply quality settings
                if quality == AudioQuality.HIGH:
                    bitrate = "320k"
                    sample_rate = 44100
                elif quality == AudioQuality.MEDIUM:
                    bitrate = "192k"
                    sample_rate = 22050
                else:  # LOW
                    bitrate = "128k"
                    sample_rate = 16000

                # Convert format
                if target_format.lower() == "mp3":
                    converted_audio = audio.set_frame_rate(sample_rate)
                    output_buffer = io.BytesIO()
                    converted_audio.export(output_buffer, format="mp3", bitrate=bitrate)
                    converted_bytes = output_buffer.getvalue()
                    
                elif target_format.lower() == "wav":
                    converted_audio = audio.set_frame_rate(sample_rate).set_channels(1)
                    output_buffer = io.BytesIO()
                    converted_audio.export(output_buffer, format="wav")
                    converted_bytes = output_buffer.getvalue()
                    
                else:
                    # Generic conversion
                    converted_audio = audio.set_frame_rate(sample_rate)
                    output_buffer = io.BytesIO()
                    converted_audio.export(output_buffer, format=target_format)
                    converted_bytes = output_buffer.getvalue()

                return {
                    "success": True,
                    "converted_audio": base64.b64encode(converted_bytes).decode('utf-8'),
                    "source_format": source_format,
                    "target_format": target_format,
                    "quality": quality.value,
                    "source_size": len(audio_data),
                    "converted_size": len(converted_bytes),
                    "compression_ratio": len(converted_bytes) / len(audio_data),
                    "metadata": {
                        "duration_ms": len(audio),
                        "sample_rate": sample_rate,
                        "channels": converted_audio.channels if 'converted_audio' in locals() else 1,
                        "bitrate": bitrate
                    }
                }

            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "audio_conversion_error"
            }

    async def validate_audio_quality(
        self, 
        audio_data: bytes, 
        min_duration_ms: int = 1000,
        max_duration_ms: int = 300000  # 5 minutes
    ) -> Dict[str, Any]:
        """
        Validate audio quality and characteristics for speech processing
        
        Args:
            audio_data: Audio bytes to validate
            min_duration_ms: Minimum required duration
            max_duration_ms: Maximum allowed duration
            
        Returns:
            Dict containing validation results and recommendations
        """
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Load audio for analysis
                audio = AudioSegment.from_file(temp_file_path)
                
                # Basic validation
                duration_ms = len(audio)
                sample_rate = audio.frame_rate
                channels = audio.channels
                
                validation_results = {
                    "is_valid": True,
                    "issues": [],
                    "recommendations": [],
                    "metadata": {
                        "duration_ms": duration_ms,
                        "sample_rate": sample_rate,
                        "channels": channels,
                        "file_size": len(audio_data)
                    }
                }

                # Duration validation
                if duration_ms < min_duration_ms:
                    validation_results["is_valid"] = False
                    validation_results["issues"].append(f"Audio too short: {duration_ms}ms < {min_duration_ms}ms")
                    validation_results["recommendations"].append("Record longer audio for better recognition")

                if duration_ms > max_duration_ms:
                    validation_results["is_valid"] = False
                    validation_results["issues"].append(f"Audio too long: {duration_ms}ms > {max_duration_ms}ms")
                    validation_results["recommendations"].append("Split audio into shorter segments")

                # Sample rate validation
                if sample_rate < 8000:
                    validation_results["issues"].append("Low sample rate may affect recognition quality")
                    validation_results["recommendations"].append("Use higher sample rate (16kHz or above)")

                # Channel validation
                if channels > 2:
                    validation_results["issues"].append("Multi-channel audio detected")
                    validation_results["recommendations"].append("Convert to mono or stereo for better processing")

                # Silence detection
                silence_analysis = await self._detect_silence_segments(audio)
                validation_results["silence_analysis"] = silence_analysis
                
                if silence_analysis["silence_percentage"] > 50:
                    validation_results["issues"].append("High silence percentage detected")
                    validation_results["recommendations"].append("Ensure clear speech throughout recording")

                # Volume analysis
                volume_analysis = await self._analyze_volume_levels(audio)
                validation_results["volume_analysis"] = volume_analysis
                
                if volume_analysis["peak_db"] < -20:
                    validation_results["issues"].append("Audio volume too low")
                    validation_results["recommendations"].append("Increase recording volume or microphone sensitivity")

                return {
                    "success": True,
                    "validation": validation_results
                }

            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Audio validation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "audio_validation_error"
            }

    async def extract_speech_features(
        self, 
        audio_data: bytes,
        feature_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Extract audio features for speech analysis and ML processing
        
        Args:
            audio_data: Audio bytes (WAV format preferred)
            feature_types: List of features to extract
            
        Returns:
            Dict containing extracted features
        """
        if feature_types is None:
            feature_types = ["mfcc", "pitch", "energy", "spectral", "rhythm"]

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Load audio with librosa
                y, sr = librosa.load(temp_file_path, sr=None)
                
                features = {}

                if "mfcc" in feature_types:
                    # Mel-frequency cepstral coefficients
                    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                    features["mfcc"] = {
                        "mean": np.mean(mfccs, axis=1).tolist(),
                        "std": np.std(mfccs, axis=1).tolist(),
                        "shape": mfccs.shape
                    }

                if "pitch" in feature_types:
                    # Pitch/F0 extraction
                    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
                    pitch_values = []
                    for t in range(pitches.shape[1]):
                        index = magnitudes[:, t].argmax()
                        pitch = pitches[index, t]
                        if pitch > 0:
                            pitch_values.append(pitch)
                    
                    features["pitch"] = {
                        "mean": float(np.mean(pitch_values)) if pitch_values else 0.0,
                        "std": float(np.std(pitch_values)) if pitch_values else 0.0,
                        "min": float(np.min(pitch_values)) if pitch_values else 0.0,
                        "max": float(np.max(pitch_values)) if pitch_values else 0.0,
                        "voiced_frames": len(pitch_values)
                    }

                if "energy" in feature_types:
                    # Energy features
                    rms = librosa.feature.rms(y=y)[0]
                    features["energy"] = {
                        "rms_mean": float(np.mean(rms)),
                        "rms_std": float(np.std(rms)),
                        "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y)))
                    }

                if "spectral" in feature_types:
                    # Spectral features
                    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
                    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
                    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
                    
                    features["spectral"] = {
                        "centroid_mean": float(np.mean(spectral_centroids)),
                        "centroid_std": float(np.std(spectral_centroids)),
                        "rolloff_mean": float(np.mean(spectral_rolloff)),
                        "rolloff_std": float(np.std(spectral_rolloff)),
                        "bandwidth_mean": float(np.mean(spectral_bandwidth)),
                        "bandwidth_std": float(np.std(spectral_bandwidth))
                    }

                if "rhythm" in feature_types:
                    # Rhythm features
                    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
                    features["rhythm"] = {
                        "tempo": float(tempo),
                        "beat_count": len(beats),
                        "rhythm_regularity": float(np.std(np.diff(beats))) if len(beats) > 1 else 0.0
                    }

                return {
                    "success": True,
                    "features": features,
                    "audio_duration": len(y) / sr,
                    "sample_rate": sr
                }

            finally:
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "feature_extraction_error"
            }

    # Private helper methods
    async def _optimize_for_speech_recognition(self, audio: AudioSegment) -> AudioSegment:
        """Optimize audio for speech recognition"""
        # Convert to mono
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Set optimal sample rate for speech recognition
        audio = audio.set_frame_rate(self.target_sample_rate)
        
        # Normalize audio
        audio = normalize(audio)
        
        # Apply dynamic range compression
        audio = compress_dynamic_range(audio)
        
        return audio

    async def _analyze_audio_quality(self, audio: AudioSegment) -> Dict[str, Any]:
        """Analyze audio quality metrics"""
        # Convert to numpy array for analysis
        samples = np.array(audio.get_array_of_samples())
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)  # Convert to mono
        
        # Calculate quality metrics
        rms = np.sqrt(np.mean(samples**2))
        peak = np.max(np.abs(samples))
        snr_estimate = 20 * np.log10(rms / (np.std(samples - np.mean(samples)) + 1e-10))
        
        return {
            "rms_level": float(rms),
            "peak_level": float(peak),
            "dynamic_range": float(peak - rms),
            "estimated_snr": float(snr_estimate),
            "quality_score": min(100, max(0, (snr_estimate + 20) * 2))  # 0-100 scale
        }

    async def _extract_audio_features(self, audio: AudioSegment) -> Dict[str, Any]:
        """Extract basic audio features"""
        return {
            "duration_seconds": len(audio) / 1000.0,
            "sample_rate": audio.frame_rate,
            "channels": audio.channels,
            "sample_width": audio.sample_width,
            "max_possible_amplitude": audio.max_possible_amplitude,
            "frame_count": audio.frame_count()
        }

    async def _audio_to_bytes(self, audio: AudioSegment, format: str = "wav") -> bytes:
        """Convert AudioSegment to bytes"""
        buffer = io.BytesIO()
        audio.export(buffer, format=format)
        return buffer.getvalue()

    async def _cache_processed_audio(
        self, 
        user_id: int, 
        audio_bytes: bytes, 
        quality_analysis: Dict
    ):
        """Cache processed audio for user"""
        try:
            redis = await self._get_redis()
            cache_key = f"processed_audio:{user_id}:{datetime.utcnow().timestamp()}"
            cache_data = {
                "audio": base64.b64encode(audio_bytes).decode('utf-8'),
                "quality": quality_analysis,
                "timestamp": datetime.utcnow().isoformat()
            }
            await redis.setex(
                cache_key,
                timedelta(hours=24).total_seconds(),
                json.dumps(cache_data)
            )
        except Exception as e:
            logger.warning(f"Failed to cache processed audio: {e}")

    def _select_best_transcription(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """Select the best transcription result from multiple engines"""
        best_result = {"transcript": "", "confidence": 0.0, "engine": "none"}
        
        for engine, result in results.items():
            if result.get("transcript") and result.get("confidence", 0) > best_result["confidence"]:
                best_result = {
                    "transcript": result["transcript"],
                    "confidence": result["confidence"],
                    "engine": engine
                }
        
        return best_result

    async def _detect_silence_segments(self, audio: AudioSegment) -> Dict[str, Any]:
        """Detect silence segments in audio"""
        # Simple silence detection based on amplitude
        silence_thresh = audio.dBFS - 16  # 16dB below average
        silence_segments = []
        
        # Analyze in 100ms chunks
        chunk_length = 100
        total_chunks = len(audio) // chunk_length
        silent_chunks = 0
        
        for i in range(0, len(audio), chunk_length):
            chunk = audio[i:i + chunk_length]
            if chunk.dBFS < silence_thresh:
                silent_chunks += 1
                silence_segments.append((i, i + chunk_length))
        
        return {
            "silence_percentage": (silent_chunks / total_chunks * 100) if total_chunks > 0 else 0,
            "silence_segments": silence_segments[:10],  # First 10 segments
            "total_silence_duration": silent_chunks * chunk_length
        }

    async def _analyze_volume_levels(self, audio: AudioSegment) -> Dict[str, Any]:
        """Analyze volume levels in audio"""
        return {
            "average_db": audio.dBFS,
            "peak_db": audio.max_dBFS,
            "rms_db": audio.rms,
            "volume_consistency": abs(audio.dBFS - audio.max_dBFS)  # Lower is more consistent
        }
