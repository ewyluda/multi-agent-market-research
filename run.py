#!/usr/bin/env python3
"""Startup script for the multi-agent market research API."""

import sys
import logging
from src.config import Config

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)

logger = logging.getLogger(__name__)


def main():
    """Start the FastAPI server."""
    # Validate configuration
    if not Config.validate_config():
        logger.error("Configuration validation failed. Please check your .env file.")
        logger.error("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    logger.info("Starting Multi-Agent Market Research API...")
    logger.info(f"Server will run on http://{Config.API_HOST}:{Config.API_PORT}")

    # Start uvicorn
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.API_RELOAD,
        log_level=Config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()
