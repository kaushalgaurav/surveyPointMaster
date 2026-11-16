import os
import logging
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_AUTH_KEY")

def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        logger.warning("Missing API key")
        raise HTTPException(status_code=401, detail="API key missing")

    if x_api_key != API_KEY:
        logger.warning("Invalid API key used: %s", x_api_key)
        raise HTTPException(status_code=403, detail="Invalid API key")

    logger.info("API key authenticated successfully")
