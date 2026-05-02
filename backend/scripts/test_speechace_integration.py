#!/usr/bin/env python3
"""
Test script for Speechace API integration.
This script tests the Speechace service initialization and basic functionality.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.speechace_service import SpeechaceService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_speechace_service():
    """Test the Speechace service initialization and basic functionality."""
    print("Testing Speechace API Integration")
    print("=" * 50)

    # Check configuration
    api_key = getattr(settings, 'SPEECHACE_API_KEY', None)
    print(f"Speechace API Key configured: {'Yes' if api_key else 'No'}")

    if not api_key:
        print("❌ SPEECHACE_API_KEY not found in environment variables")
        print("Please set SPEECHACE_API_KEY in your .env file")
        return False

    # Initialize service
    try:
        service = SpeechaceService()
        print("✅ Speechace service initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Speechace service: {e}")
        return False

    # Test service attributes
    print(f"API Key configured: {'Yes' if service.api_key else 'No'}")
    print(f"Base URL: {service.base_url}")
    print(f"Use Speechace: {service.use_speechace}")

    # Test audio validation (without actual audio file)
    try:
        # Test with empty bytes (should fail validation)
        is_valid, error_msg = await service.validate_audio_format(b"")
        print(f"Empty audio validation: {'Valid' if is_valid else 'Invalid'} - {error_msg}")

        # Test with minimal WAV header
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x01\x00\x08\x00data\x00\x08\x00\x00'
        is_valid, error_msg = await service.validate_audio_format(wav_header)
        print(f"WAV header validation: {'Valid' if is_valid else 'Invalid'} - {error_msg}")

    except Exception as e:
        print(f"❌ Audio validation test failed: {e}")
        return False

    # Test supported languages
    try:
        languages = await service.get_supported_languages()
        print(f"✅ Supported languages: {len(languages)} languages")
        print(f"Sample languages: {languages[:5]}")
    except Exception as e:
        print(f"❌ Failed to get supported languages: {e}")
        return False

    print("\n✅ Speechace integration test completed successfully!")
    print("\nNext steps:")
    print("1. Add your Speechace API key to the .env file")
    print("2. Test with actual audio files using the API endpoints")
    print("3. Verify pronunciation assessment results")

    return True


if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_speechace_service())
    sys.exit(0 if success else 1)





















