import asyncio
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
import pickle
import zlib
from functools import wraps

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheStrategy(str, Enum):
    """Cache strategies for different types of data"""
    LRU = "lru"              # Least Recently Used
    LFU = "lfu"              # Least Frequently Used
    TTL = "ttl"              # Time To Live
    WRITE_THROUGH = "write_through"    # Write to cache and DB simultaneously
    WRITE_BACK = "write_back"          # Write to cache first, DB later
    READ_THROUGH = "read_through"      # Read from cache, fallback to DB

class CacheLevel(str, Enum):
    """Cache levels with different performance characteristics"""
    L1_MEMORY = "l1_memory"      # In-memory cache (fastest)
    L2_REDIS = "l2_redis"        # Redis cache (fast)
    L3_DATABASE = "l3_database"  # Database cache (slower)

class AdvancedCachingService:
    """
    Advanced multi-level caching service with intelligent cache strategies
    for AI responses, user data, and content optimization
    """
    
    def __init__(self):
        # Redis connection
        self.redis_client = None
        self.redis_url = settings.REDIS_URL
        
        # In-memory L1 cache (limited size)
        self.l1_cache: Dict[str, Any] = {}
        self.l1_access_count: Dict[str, int] = {}
        self.l1_last_access: Dict[str, datetime] = {}
        self.l1_max_size = 1000  # Maximum L1 cache entries
        
        # Cache configuration
        self.default_ttl = timedelta(hours=1)
        self.ai_response_ttl = timedelta(hours=6)
        self.user_data_ttl = timedelta(hours=24)
        self.content_ttl = timedelta(days=7)
        
        # Compression settings
        self.compression_threshold = 1024  # Compress data larger than 1KB
        self.compression_level = 6  # zlib compression level
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if not self.redis_client:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle encoding ourselves
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return self.redis_client

    async def get(
        self,
        key: str,
        cache_level: CacheLevel = CacheLevel.L2_REDIS,
        fallback_func: Optional[Callable] = None,
        ttl: Optional[timedelta] = None
    ) -> Optional[Any]:
        """
        Get value from cache with multi-level fallback
        
        Args:
            key: Cache key
            cache_level: Preferred cache level
            fallback_func: Function to call if cache miss
            ttl: TTL for storing fallback result
            
        Returns:
            Cached value or None
        """
        try:
            # Try L1 cache first (always check for hot data)
            if key in self.l1_cache:
                self._update_l1_access(key)
                logger.debug(f"L1 cache hit: {key}")
                return self.l1_cache[key]
            
            # Try L2 Redis cache
            if cache_level in [CacheLevel.L2_REDIS, CacheLevel.L3_DATABASE]:
                redis_client = await self._get_redis()
                cached_data = await redis_client.get(f"cache:{key}")
                
                if cached_data:
                    try:
                        # Decompress if needed
                        if cached_data.startswith(b'COMPRESSED:'):
                            compressed_data = cached_data[11:]  # Remove 'COMPRESSED:' prefix
                            decompressed_data = zlib.decompress(compressed_data)
                            value = pickle.loads(decompressed_data)
                        else:
                            value = pickle.loads(cached_data)
                        
                        # Store in L1 cache for faster future access
                        await self._store_l1(key, value)
                        
                        logger.debug(f"L2 cache hit: {key}")
                        return value
                    except Exception as e:
                        logger.error(f"Error deserializing cached data for {key}: {e}")
                        # Remove corrupted cache entry
                        await redis_client.delete(f"cache:{key}")
            
            # Cache miss - use fallback function if provided
            if fallback_func:
                logger.debug(f"Cache miss, using fallback for: {key}")
                value = await fallback_func() if asyncio.iscoroutinefunction(fallback_func) else fallback_func()
                
                # Store the result in cache
                if value is not None:
                    await self.set(key, value, ttl or self.default_ttl)
                
                return value
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: timedelta = None,
        cache_level: CacheLevel = CacheLevel.L2_REDIS,
        strategy: CacheStrategy = CacheStrategy.TTL
    ) -> bool:
        """
        Set value in cache with specified strategy
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live
            cache_level: Cache level to use
            strategy: Caching strategy
            
        Returns:
            True if successfully cached
        """
        try:
            ttl = ttl or self.default_ttl
            
            # Store in L1 cache
            await self._store_l1(key, value)
            
            # Store in L2 Redis cache
            if cache_level in [CacheLevel.L2_REDIS, CacheLevel.L3_DATABASE]:
                redis_client = await self._get_redis()
                
                # Serialize data
                serialized_data = pickle.dumps(value)
                
                # Compress large data
                if len(serialized_data) > self.compression_threshold:
                    compressed_data = zlib.compress(serialized_data, self.compression_level)
                    cache_data = b'COMPRESSED:' + compressed_data
                    logger.debug(f"Compressed cache data for {key}: {len(serialized_data)} -> {len(compressed_data)} bytes")
                else:
                    cache_data = serialized_data
                
                # Set with TTL
                await redis_client.setex(
                    f"cache:{key}",
                    int(ttl.total_seconds()),
                    cache_data
                )
                
                # Update cache metadata
                await self._update_cache_metadata(key, strategy, ttl)
            
            logger.debug(f"Cached {key} with TTL {ttl}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels"""
        try:
            success = True
            
            # Delete from L1 cache
            if key in self.l1_cache:
                del self.l1_cache[key]
                self.l1_access_count.pop(key, None)
                self.l1_last_access.pop(key, None)
            
            # Delete from L2 Redis cache
            redis_client = await self._get_redis()
            result = await redis_client.delete(f"cache:{key}")
            
            # Delete metadata
            await redis_client.delete(f"cache_meta:{key}")
            
            logger.debug(f"Deleted cache key: {key}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def get_ai_response(
        self,
        prompt_hash: str,
        model: str,
        parameters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached AI response"""
        cache_key = self._generate_ai_cache_key(prompt_hash, model, parameters)
        return await self.get(cache_key, ttl=self.ai_response_ttl)

    async def cache_ai_response(
        self,
        prompt_hash: str,
        model: str,
        parameters: Dict[str, Any],
        response: Dict[str, Any]
    ) -> bool:
        """Cache AI response with intelligent TTL"""
        cache_key = self._generate_ai_cache_key(prompt_hash, model, parameters)
        
        # Adjust TTL based on response quality and type
        ttl = self.ai_response_ttl
        if response.get("confidence", 0) > 0.9:
            ttl = timedelta(days=1)  # High confidence responses cached longer
        elif response.get("type") == "conversation":
            ttl = timedelta(hours=2)  # Conversation responses cached shorter
        
        return await self.set(cache_key, response, ttl)

    async def get_user_data(self, user_id: int, data_type: str) -> Optional[Any]:
        """Get cached user data"""
        cache_key = f"user:{user_id}:{data_type}"
        return await self.get(cache_key, ttl=self.user_data_ttl)

    async def cache_user_data(
        self,
        user_id: int,
        data_type: str,
        data: Any,
        ttl: Optional[timedelta] = None
    ) -> bool:
        """Cache user data"""
        cache_key = f"user:{user_id}:{data_type}"
        return await self.set(cache_key, data, ttl or self.user_data_ttl)

    async def get_content(self, content_id: str, content_type: str) -> Optional[Any]:
        """Get cached content"""
        cache_key = f"content:{content_type}:{content_id}"
        return await self.get(cache_key, ttl=self.content_ttl)

    async def cache_content(
        self,
        content_id: str,
        content_type: str,
        content: Any
    ) -> bool:
        """Cache content with long TTL"""
        cache_key = f"content:{content_type}:{content_id}"
        return await self.set(cache_key, content, self.content_ttl)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        try:
            redis_client = await self._get_redis()
            
            # Get keys matching pattern
            keys = await redis_client.keys(f"cache:{pattern}")
            
            if keys:
                # Delete matching keys
                deleted_count = await redis_client.delete(*keys)
                
                # Also clean up from L1 cache
                pattern_without_prefix = pattern.replace("cache:", "")
                l1_keys_to_delete = [k for k in self.l1_cache.keys() if pattern_without_prefix in k]
                for key in l1_keys_to_delete:
                    del self.l1_cache[key]
                    self.l1_access_count.pop(key, None)
                    self.l1_last_access.pop(key, None)
                
                logger.info(f"Invalidated {deleted_count} cache keys matching pattern: {pattern}")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Pattern invalidation error for {pattern}: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        try:
            redis_client = await self._get_redis()
            
            # Redis info
            redis_info = await redis_client.info()
            
            # L1 cache stats
            l1_stats = {
                "size": len(self.l1_cache),
                "max_size": self.l1_max_size,
                "hit_rate": self._calculate_l1_hit_rate(),
                "most_accessed": sorted(
                    self.l1_access_count.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            }
            
            # Cache key distribution
            all_keys = await redis_client.keys("cache:*")
            key_types = {}
            for key in all_keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                key_type = key_str.split(":")[1] if ":" in key_str else "unknown"
                key_types[key_type] = key_types.get(key_type, 0) + 1
            
            return {
                "l1_cache": l1_stats,
                "redis_info": {
                    "used_memory": redis_info.get("used_memory_human", "N/A"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "total_commands_processed": redis_info.get("total_commands_processed", 0)
                },
                "key_distribution": key_types,
                "total_cached_keys": len(all_keys)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

    async def precompute_user_recommendations(self, user_id: int) -> bool:
        """Precompute and cache user recommendations"""
        try:
            # This would typically call your recommendation engine
            # For now, we'll create a mock structure
            recommendations = {
                "exercises": [
                    {"type": "vocabulary", "difficulty": "intermediate", "topic": "business"},
                    {"type": "grammar", "difficulty": "intermediate", "topic": "conditionals"}
                ],
                "content": [
                    {"type": "reading", "level": "B2", "topic": "technology"},
                    {"type": "listening", "level": "B2", "topic": "daily_life"}
                ],
                "next_lesson": {
                    "type": "conversation",
                    "topic": "job_interview",
                    "estimated_duration": 25
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
            cache_key = f"recommendations:{user_id}"
            return await self.set(cache_key, recommendations, timedelta(hours=6))
            
        except Exception as e:
            logger.error(f"Error precomputing recommendations for user {user_id}: {e}")
            return False

    async def warm_cache(self, cache_keys: List[str]) -> Dict[str, bool]:
        """Warm cache with frequently accessed data"""
        results = {}
        
        for key in cache_keys:
            try:
                # Check if key exists and refresh TTL
                redis_client = await self._get_redis()
                exists = await redis_client.exists(f"cache:{key}")
                
                if exists:
                    # Refresh TTL
                    await redis_client.expire(f"cache:{key}", int(self.default_ttl.total_seconds()))
                    results[key] = True
                else:
                    results[key] = False
                    
            except Exception as e:
                logger.error(f"Error warming cache for {key}: {e}")
                results[key] = False
        
        return results

    # Private helper methods
    async def _store_l1(self, key: str, value: Any):
        """Store value in L1 cache with eviction"""
        # Check if we need to evict
        if len(self.l1_cache) >= self.l1_max_size:
            await self._evict_l1()
        
        self.l1_cache[key] = value
        self.l1_access_count[key] = self.l1_access_count.get(key, 0) + 1
        self.l1_last_access[key] = datetime.utcnow()

    async def _evict_l1(self):
        """Evict least recently used items from L1 cache"""
        if not self.l1_last_access:
            return
        
        # Find least recently used key
        lru_key = min(self.l1_last_access.items(), key=lambda x: x[1])[0]
        
        # Remove from all L1 structures
        self.l1_cache.pop(lru_key, None)
        self.l1_access_count.pop(lru_key, None)
        self.l1_last_access.pop(lru_key, None)

    def _update_l1_access(self, key: str):
        """Update L1 cache access statistics"""
        self.l1_access_count[key] = self.l1_access_count.get(key, 0) + 1
        self.l1_last_access[key] = datetime.utcnow()

    def _calculate_l1_hit_rate(self) -> float:
        """Calculate L1 cache hit rate"""
        total_accesses = sum(self.l1_access_count.values())
        return len(self.l1_cache) / max(total_accesses, 1)

    def _generate_ai_cache_key(
        self, 
        prompt_hash: str, 
        model: str, 
        parameters: Dict[str, Any]
    ) -> str:
        """Generate cache key for AI responses"""
        param_str = json.dumps(parameters, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"ai:{model}:{prompt_hash}:{param_hash}"

    async def _update_cache_metadata(
        self, 
        key: str, 
        strategy: CacheStrategy, 
        ttl: timedelta
    ):
        """Update cache metadata for analytics"""
        try:
            redis_client = await self._get_redis()
            metadata = {
                "strategy": strategy.value,
                "created_at": datetime.utcnow().isoformat(),
                "ttl_seconds": int(ttl.total_seconds()),
                "access_count": 1
            }
            
            await redis_client.setex(
                f"cache_meta:{key}",
                int(ttl.total_seconds()),
                json.dumps(metadata)
            )
            
        except Exception as e:
            logger.error(f"Error updating cache metadata for {key}: {e}")

    async def cleanup_expired_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries and metadata"""
        try:
            redis_client = await self._get_redis()
            
            # Get all cache keys
            cache_keys = await redis_client.keys("cache:*")
            meta_keys = await redis_client.keys("cache_meta:*")
            
            expired_cache = 0
            expired_meta = 0
            
            # Check and clean expired cache keys
            for key in cache_keys:
                ttl = await redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist or expired
                    expired_cache += 1
            
            # Check and clean expired metadata
            for key in meta_keys:
                ttl = await redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist or expired
                    expired_meta += 1
            
            # Clean up L1 cache of old entries
            current_time = datetime.utcnow()
            l1_cleaned = 0
            
            keys_to_remove = []
            for key, last_access in self.l1_last_access.items():
                if current_time - last_access > timedelta(hours=1):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self.l1_cache.pop(key, None)
                self.l1_access_count.pop(key, None)
                self.l1_last_access.pop(key, None)
                l1_cleaned += 1
            
            return {
                "expired_cache_keys": expired_cache,
                "expired_metadata_keys": expired_meta,
                "l1_cleaned_keys": l1_cleaned
            }
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return {"error": str(e)}

# Decorator for automatic caching
def cache_result(
    key_func: Callable = None,
    ttl: timedelta = None,
    cache_level: CacheLevel = CacheLevel.L2_REDIS
):
    """
    Decorator to automatically cache function results
    
    Args:
        key_func: Function to generate cache key from args
        ttl: Time to live for cached result
        cache_level: Cache level to use
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                func_name = func.__name__
                args_str = str(args) + str(sorted(kwargs.items()))
                args_hash = hashlib.md5(args_str.encode()).hexdigest()
                cache_key = f"func:{func_name}:{args_hash}"
            
            # Try to get from cache
            caching_service = AdvancedCachingService()
            cached_result = await caching_service.get(cache_key, cache_level)
            
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await caching_service.set(cache_key, result, ttl or timedelta(hours=1), cache_level)
            
            return result
        
        return wrapper
    return decorator

# Global caching service instance
caching_service = AdvancedCachingService()
