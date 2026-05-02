"""
DigitalOcean Spaces Storage Service
Provides S3-compatible object storage for audio files, images, and other media.
"""

import logging
import os
from typing import Optional
from botocore.exceptions import NoCredentialsError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for uploading and managing files in DigitalOcean Spaces.
    Uses boto3 with S3-compatible API.
    """
    
    def __init__(self):
        self._client = None
        self._initialized = False
        self._init_error = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the S3/Spaces client lazily"""
        # Log all Spaces-related settings for debugging (without secrets)
        logger.info("=" * 60)
        logger.info("DigitalOcean Spaces Configuration Check:")
        logger.info(f"  SPACES_KEY: {'SET (' + settings.SPACES_KEY[:4] + '...)' if settings.SPACES_KEY else 'NOT SET'}")
        logger.info(f"  SPACES_SECRET: {'SET (****)' if settings.SPACES_SECRET else 'NOT SET'}")
        logger.info(f"  SPACES_BUCKET: {settings.SPACES_BUCKET or 'NOT SET'}")
        logger.info(f"  SPACES_REGION: {settings.SPACES_REGION or 'NOT SET'}")
        logger.info(f"  SPACES_ENDPOINT: {settings.SPACES_ENDPOINT or 'NOT SET'}")
        logger.info(f"  SPACES_CDN_ENDPOINT: {settings.SPACES_CDN_ENDPOINT or 'NOT SET'}")
        logger.info(f"  AUDIO_STORAGE_MODE: {getattr(settings, 'AUDIO_STORAGE_MODE', 'filesystem')}")
        logger.info("=" * 60)
        
        # Check if all required settings are available
        missing = []
        if not settings.SPACES_KEY:
            missing.append("SPACES_KEY")
        if not settings.SPACES_SECRET:
            missing.append("SPACES_SECRET")
        if not settings.SPACES_BUCKET:
            missing.append("SPACES_BUCKET")
        if not settings.SPACES_ENDPOINT:
            missing.append("SPACES_ENDPOINT")
        
        if missing:
            self._init_error = f"Missing required Spaces settings: {', '.join(missing)}"
            logger.warning(
                f"DigitalOcean Spaces not configured. {self._init_error}. "
                "Files will be stored locally."
            )
            return
        
        # Validate endpoint format - should NOT contain bucket name
        # Correct format: https://nyc3.digitaloceanspaces.com
        # Incorrect format: https://bucket-name.nyc3.digitaloceanspaces.com
        if settings.SPACES_ENDPOINT and settings.SPACES_BUCKET:
            if settings.SPACES_BUCKET in settings.SPACES_ENDPOINT:
                logger.warning(
                    f"⚠️ SPACES_ENDPOINT appears to contain the bucket name '{settings.SPACES_BUCKET}'. "
                    f"The endpoint should be 'https://{settings.SPACES_REGION}.digitaloceanspaces.com' "
                    f"(without the bucket name). The bucket name should only be in SPACES_BUCKET."
                )
        
        try:
            import boto3
            from botocore.config import Config
            
            session = boto3.session.Session()
            self._client = session.client(
                's3',
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.SPACES_ENDPOINT,
                aws_access_key_id=settings.SPACES_KEY,
                aws_secret_access_key=settings.SPACES_SECRET,
                config=Config(
                    signature_version='s3v4',
                    retries={'max_attempts': 3, 'mode': 'standard'}
                )
            )
            
            # Test the connection by listing bucket (head_bucket)
            try:
                self._client.head_bucket(Bucket=settings.SPACES_BUCKET)
                self._initialized = True
                logger.info(f"✅ DigitalOcean Spaces client initialized and connected to bucket: {settings.SPACES_BUCKET}")
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == '404':
                    self._init_error = f"Bucket '{settings.SPACES_BUCKET}' does not exist"
                elif error_code == '403':
                    self._init_error = f"Access denied to bucket '{settings.SPACES_BUCKET}'. Check your credentials and permissions."
                else:
                    self._init_error = f"Cannot access bucket: {error_code} - {str(e)}"
                logger.error(f"❌ Spaces connection failed: {self._init_error}")
                self._client = None
                
        except ImportError:
            self._init_error = "boto3 is not installed"
            logger.error("boto3 is not installed. Run: pip install boto3")
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Failed to initialize Spaces client: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if the storage service is available and configured"""
        available = self._initialized and self._client is not None
        if not available and self._init_error:
            logger.debug(f"Spaces not available: {self._init_error}")
        return available
    
    @property
    def init_error(self) -> Optional[str]:
        """Return the initialization error message if any"""
        return self._init_error
    
    def get_status(self) -> dict:
        """Get detailed status of the storage service"""
        return {
            "available": self.is_available,
            "initialized": self._initialized,
            "error": self._init_error,
            "bucket": settings.SPACES_BUCKET if settings.SPACES_BUCKET else None,
            "region": settings.SPACES_REGION,
            "endpoint": settings.SPACES_ENDPOINT if settings.SPACES_ENDPOINT else None,
            "cdn_endpoint": settings.SPACES_CDN_ENDPOINT if settings.SPACES_CDN_ENDPOINT else None,
        }
    
    def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """
        Uploads bytes to DigitalOcean Spaces and returns the public URL.
        
        Args:
            file_content: The file content as bytes
            destination_path: The path/key in the bucket (e.g., "audio/user123/file.wav")
            content_type: MIME type of the file (e.g., "audio/wav", "image/png")
        
        Returns:
            The public URL of the uploaded file, or None if upload failed
        """
        if not self.is_available:
            logger.error("Storage service not available. Check configuration.")
            return None
        
        bucket_name = settings.SPACES_BUCKET
        
        try:
            # Upload the file with public-read ACL
            self._client.put_object(
                Bucket=bucket_name,
                Key=destination_path,
                Body=file_content,
                ACL='public-read',
                ContentType=content_type,
                # Optional: Set cache control for better CDN performance
                CacheControl='public, max-age=31536000'  # Cache for 1 year
            )
            
            # Construct the public URL
            # Use CDN endpoint if available, otherwise use standard endpoint
            if settings.SPACES_CDN_ENDPOINT:
                # CDN URL format: https://bucket.region.cdn.digitaloceanspaces.com/path
                cdn_base = settings.SPACES_CDN_ENDPOINT.rstrip('/')
                url = f"{cdn_base}/{destination_path}"
            else:
                # Standard URL format: https://bucket.region.digitaloceanspaces.com/path
                url = f"https://{bucket_name}.{settings.SPACES_REGION}.digitaloceanspaces.com/{destination_path}"
            
            logger.info(f"File uploaded successfully to: {destination_path}")
            return url
            
        except NoCredentialsError:
            logger.error("Credentials not available for Spaces upload")
            return None
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"Spaces upload failed (ClientError {error_code}): {e}")
            return None
        except Exception as e:
            logger.error(f"Error uploading to Spaces: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from DigitalOcean Spaces.
        
        Args:
            file_path: The path/key of the file to delete
        
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.is_available:
            logger.error("Storage service not available. Check configuration.")
            return False
        
        try:
            self._client.delete_object(
                Bucket=settings.SPACES_BUCKET,
                Key=file_path
            )
            logger.info(f"File deleted successfully: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from Spaces: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in DigitalOcean Spaces.
        
        Args:
            file_path: The path/key of the file to check
        
        Returns:
            True if the file exists, False otherwise
        """
        if not self.is_available:
            return False
        
        try:
            self._client.head_object(
                Bucket=settings.SPACES_BUCKET,
                Key=file_path
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False
    
    def get_public_url(self, file_path: str) -> str:
        """
        Get the public URL for a file in Spaces.
        
        Args:
            file_path: The path/key of the file
        
        Returns:
            The public URL
        """
        if settings.SPACES_CDN_ENDPOINT:
            cdn_base = settings.SPACES_CDN_ENDPOINT.rstrip('/')
            return f"{cdn_base}/{file_path}"
        
        return f"https://{settings.SPACES_BUCKET}.{settings.SPACES_REGION}.digitaloceanspaces.com/{file_path}"


# Global singleton instance
storage_service = StorageService()







