"""Rate limiting utilities for API calls."""

import asyncio
import logging
import time
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter to enforce request rate limits and minimum delays between requests.
    
    Supports both per-minute and per-hour rate limits.
    """
    
    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        min_delay_between_requests: float = 0.0,
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests per minute (None = no limit)
            requests_per_hour: Maximum number of requests per hour (None = no limit)
            min_delay_between_requests: Minimum delay in seconds between consecutive requests
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.min_delay = min_delay_between_requests
        
        # Track request timestamps
        self.minute_requests: deque = deque()
        self.hour_requests: deque = deque()
        self.last_request_time: Optional[float] = None
    
    async def acquire(self) -> None:
        """
        Wait until a request can be made while respecting rate limits.
        
        This method will block (async wait) if necessary to enforce:
        1. Minimum delay between requests
        2. Requests per minute limit
        3. Requests per hour limit
        """
        current_time = time.time()
        
        # Enforce minimum delay between requests
        if self.last_request_time is not None and self.min_delay > 0:
            elapsed = current_time - self.last_request_time
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                logger.debug(f"Rate limiter: waiting {wait_time:.2f}s for min_delay")
                await asyncio.sleep(wait_time)
                current_time = time.time()
        
        # Enforce requests-per-minute limit
        if self.requests_per_minute is not None:
            # Remove requests older than 1 minute
            minute_ago = current_time - 60
            while self.minute_requests and self.minute_requests[0] < minute_ago:
                self.minute_requests.popleft()
            
            # Wait if we've hit the limit
            if len(self.minute_requests) >= self.requests_per_minute:
                oldest_request = self.minute_requests[0]
                wait_time = 60 - (current_time - oldest_request)
                if wait_time > 0:
                    logger.debug(f"Rate limiter: waiting {wait_time:.2f}s for per-minute limit")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                    # Clean up again after waiting
                    minute_ago = current_time - 60
                    while self.minute_requests and self.minute_requests[0] < minute_ago:
                        self.minute_requests.popleft()
        
        # Enforce requests-per-hour limit
        if self.requests_per_hour is not None:
            # Remove requests older than 1 hour
            hour_ago = current_time - 3600
            while self.hour_requests and self.hour_requests[0] < hour_ago:
                self.hour_requests.popleft()
            
            # Wait if we've hit the limit
            if len(self.hour_requests) >= self.requests_per_hour:
                oldest_request = self.hour_requests[0]
                wait_time = 3600 - (current_time - oldest_request)
                if wait_time > 0:
                    logger.debug(f"Rate limiter: waiting {wait_time:.2f}s for per-hour limit")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                    # Clean up again after waiting
                    hour_ago = current_time - 3600
                    while self.hour_requests and self.hour_requests[0] < hour_ago:
                        self.hour_requests.popleft()
        
        # Record this request
        self.last_request_time = current_time
        if self.requests_per_minute is not None:
            self.minute_requests.append(current_time)
        if self.requests_per_hour is not None:
            self.hour_requests.append(current_time)
    
    def reset(self) -> None:
        """Reset all rate limiting state."""
        self.minute_requests.clear()
        self.hour_requests.clear()
        self.last_request_time = None


def create_rate_limiter_from_config(config: dict, service: str) -> Optional[RateLimiter]:
    """
    Create a rate limiter from configuration.
    
    Args:
        config: Agent configuration dictionary
        service: Service name (e.g., 'github', 'jira', 'confluence')
    
    Returns:
        RateLimiter instance or None if no rate limiting configured
    """
    rate_limits = config.get("rate_limits", {}).get(service, {})
    
    if not rate_limits:
        return None
    
    return RateLimiter(
        requests_per_minute=rate_limits.get("requests_per_minute"),
        requests_per_hour=rate_limits.get("requests_per_hour"),
        min_delay_between_requests=rate_limits.get("min_delay_between_requests", 0.0),
    )
