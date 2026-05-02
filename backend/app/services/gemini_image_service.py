"""
Gemini Image Generation Service
Uses gemini-2.5-flash-image for generating images for speaking exercises.
"""

import asyncio
import base64
import hashlib
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

import google.generativeai as genai
from google.generativeai import types

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_storage_service():
    """Lazy-load the storage service to avoid circular imports"""
    from app.services.storage_service import storage_service
    return storage_service

# Singleton instance
_image_service_instance: Optional["GeminiImageService"] = None


class GeminiImageService:
    """
    Image generation service using Gemini 2.0 Flash experimental model.
    Generates small images suitable for language learning exercises.
    """
    
    def __init__(self):
        """Initialize Gemini API client for image generation"""
        self._client = None
        self._image_model = None
        
        try:
            api_key = getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GOOGLE_GEMINI_API_KEY not found. Image generation unavailable.")
                return
            
            genai.configure(api_key=api_key)
            # Use gemini-2.5-flash-image for image generation (imagen-3.0 is the image model)
            self._image_model = genai.GenerativeModel("gemini-2.5-flash-image")
            logger.info("Gemini image generation service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini image service: {e}")
            self._image_model = None
    
    @property
    def is_available(self) -> bool:
        """Check if the image generation service is available"""
        return self._image_model is not None
    
    async def generate_speaking_image(
        self,
        prompt: str,
        speaking_type: str = "conversation",
        user_level: str = "B1",
    ) -> Dict[str, Any]:
        """
        Generate an image for a speaking exercise prompt.
        
        Args:
            prompt: The speaking exercise prompt/topic
            speaking_type: Type of speaking exercise (pronunciation, conversation, etc.)
            user_level: CEFR level of the user
            
        Returns:
            Dict with image_url, image_data (base64), or error
        """
        if not self.is_available:
            return {"success": False, "error": "Image generation service not available"}
        
        try:
            # Create an optimized prompt for image generation
            image_prompt = self._create_image_prompt(prompt, speaking_type, user_level)
            
            logger.info(f"Generating image for speaking exercise: {prompt[:50]}...")
            
            # Generate image using Gemini
            response = await asyncio.to_thread(
                self._image_model.generate_content,
                [image_prompt],
                generation_config=types.GenerationConfig(
                    response_mime_type="image/png",
                )
            )
            
            # Check if we got an image response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Save the image
                            image_data = part.inline_data.data
                            image_url = await self._save_image(image_data, prompt)
                            
                            return {
                                "success": True,
                                "image_url": image_url,
                                "image_data": base64.b64encode(image_data).decode('utf-8'),
                                "prompt_used": image_prompt,
                            }
            
            # If direct image generation fails, try with Imagen through Gemini
            return await self._generate_with_text_prompt(prompt, speaking_type, user_level)
            
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_with_text_prompt(
        self,
        prompt: str,
        speaking_type: str,
        user_level: str,
    ) -> Dict[str, Any]:
        """
        Alternative method: Generate image description and use placeholder.
        Returns a description that can be used with external image services.
        """
        try:
            # Generate a detailed image description
            description_prompt = f"""Create a brief, simple image description for a language learning exercise.

Topic: {prompt}
Exercise Type: {speaking_type}
User Level: {user_level}

Generate a 1-2 sentence description of a simple, educational illustration that would help a language learner practice this speaking topic. 
Focus on clear, concrete visuals that are easy to describe and discuss.
Keep it simple and culturally neutral."""

            response = await asyncio.to_thread(
                self._image_model.generate_content,
                description_prompt
            )
            
            if response.text:
                return {
                    "success": True,
                    "image_description": response.text.strip(),
                    "fallback": True,
                    "message": "Image description generated (direct image generation not available)"
                }
            
            return {"success": False, "error": "Could not generate image or description"}
            
        except Exception as e:
            logger.error(f"Text-based image generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_image_prompt(self, prompt: str, speaking_type: str, user_level: str) -> str:
        """Create an optimized prompt for image generation"""
        
        type_context = {
            "pronunciation": "a simple illustration showing a person speaking clearly",
            "conversation": "a friendly scene showing two people having a conversation",
            "description": "a clear scene that someone would describe in detail",
            "storytelling": "an engaging scene that tells a simple story",
            "presentation": "a professional setting with visual aids",
        }
        
        context = type_context.get(speaking_type, "a clear educational illustration")
        
        return f"""Generate a simple, clean educational illustration:

Topic: {prompt}
Style: {context}

Requirements:
- Simple, cartoon-like style suitable for language learning
- Bright, friendly colors
- No text in the image
- Clear subject matter that is easy to describe
- Culturally neutral content
- Small size (256x256 pixels or similar)
- Professional and educational appearance"""

    async def _save_image(self, image_data: bytes, prompt: str) -> str:
        """Save the generated image and return its URL"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            filename = f"speaking_img_{timestamp}_{prompt_hash}.png"
            
            # Check if we should use DigitalOcean Spaces
            storage_mode = getattr(settings, "AUDIO_STORAGE_MODE", "filesystem")
            
            if storage_mode == "spaces":
                storage_service = _get_storage_service()
                
                if storage_service.is_available:
                    # Upload to Spaces: images/speaking/{filename}
                    destination_path = f"images/speaking/{filename}"
                    public_url = storage_service.upload_file(
                        file_content=image_data,
                        destination_path=destination_path,
                        content_type="image/png"
                    )
                    
                    if public_url:
                        logger.info(f"Image uploaded to Spaces: {destination_path}")
                        return public_url
                    else:
                        logger.warning("Spaces upload failed, falling back to filesystem")
                else:
                    logger.warning("Spaces not configured, falling back to filesystem")
            
            # Fallback: Local filesystem storage
            storage_dir = os.path.join(
                getattr(settings, 'STORAGE_PATH', 'storage'),
                'images',
                'speaking'
            )
            os.makedirs(storage_dir, exist_ok=True)
            
            filepath = os.path.join(storage_dir, filename)
            
            # Save image locally
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            # Return URL path (served by FastAPI static mount)
            public_base = getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")
            return f"{public_base}/static/images/speaking/{filename}"
            
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            raise


async def get_image_service() -> GeminiImageService:
    """Get or create the singleton image service instance"""
    global _image_service_instance
    
    if _image_service_instance is None:
        _image_service_instance = GeminiImageService()
    
    return _image_service_instance






