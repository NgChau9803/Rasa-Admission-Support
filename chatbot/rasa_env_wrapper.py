import os
import sys
from dotenv import load_dotenv

# Force load the .env file
load_dotenv()

# --- GEMINI API KEY ROTATION FOR RASA CALM ---
import logging
logger = logging.getLogger(__name__)

google_keys = [v.strip() for k, v in os.environ.items() if k.startswith("GOOGLE_API_KEY") and v.strip()]

# Initialize with the first key to satisfy Rasa's startup validator/health check
if google_keys:
    os.environ["GOOGLE_API_KEY"] = google_keys[0]
    os.environ["GEMINI_API_KEY"] = google_keys[0]

if len(google_keys) > 1:
    logger.info(f"\n[INFO] Enabled API Key Rotation with {len(google_keys)} keys for Rasa CALM.\n")
    try:
        import litellm
        from litellm.exceptions import RateLimitError, ServiceUnavailableError
        import itertools
        
        key_cycle = itertools.cycle(google_keys)
        orig_acompletion = litellm.acompletion
        orig_completion = litellm.completion

        async def patched_acompletion(*args, **kwargs):
            attempts = 0
            max_attempts = len(google_keys)
            # Force litellm to not retry internally, so we can handle rotation immediately
            kwargs["num_retries"] = 0
            while attempts < max_attempts:
                current_key = next(key_cycle)
                kwargs["api_key"] = current_key
                # Sync the key to environment for underlying SDKs that read directly from env
                os.environ["GOOGLE_API_KEY"] = current_key
                os.environ["GEMINI_API_KEY"] = current_key
                try:
                    return await orig_acompletion(*args, **kwargs)
                except (RateLimitError, ServiceUnavailableError) as e:
                    attempts += 1
                    logger.warning(f"[RateLimit/503] Key failed. Rotating... (Attempt {attempts}/{max_attempts})")
                    if attempts >= max_attempts:
                        raise e

        def patched_completion(*args, **kwargs):
            attempts = 0
            max_attempts = len(google_keys)
            # Force litellm to not retry internally, so we can handle rotation immediately
            kwargs["num_retries"] = 0
            while attempts < max_attempts:
                current_key = next(key_cycle)
                kwargs["api_key"] = current_key
                # Sync the key to environment for underlying SDKs that read directly from env
                os.environ["GOOGLE_API_KEY"] = current_key
                os.environ["GEMINI_API_KEY"] = current_key
                try:
                    return orig_completion(*args, **kwargs)
                except (RateLimitError, ServiceUnavailableError) as e:
                    attempts += 1
                    logger.warning(f"[RateLimit/503] Key failed. Rotating... (Attempt {attempts}/{max_attempts})")
                    if attempts >= max_attempts:
                        raise e
                        
        litellm.acompletion = patched_acompletion
        litellm.completion = patched_completion
    except ImportError:
        pass

# Run the Rasa CLI
from rasa.__main__ import main
sys.exit(main())
