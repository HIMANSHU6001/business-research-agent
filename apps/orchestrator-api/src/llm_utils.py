import os
import random
from langchain_groq import ChatGroq

# Model Configurations
SUPERVISOR_MODEL = "openai/gpt-oss-120b"
QUANTITATIVE_MODEL = "openai/gpt-oss-120b"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

def get_chat_groq(model: str = DEFAULT_MODEL, temperature: float = 0.1, **kwargs) -> ChatGroq:
    """Initialize a ChatGroq model using API key from the environment."""

    # Collect all available GROQ API keys from environment
    groq_keys = [v for k, v in os.environ.items() if k.startswith("GROQ_API_KEY") and v.strip()]
    
    if not groq_keys:
        # Fallback to single GROQ_API_KEY if the numbered ones are not found but this is set
        base_key = os.getenv("GROQ_API_KEY")
        if base_key:
            groq_keys.append(base_key)
        else:
            raise ValueError("No GROQ_API_KEY found in environment variables.")

    api_key = random.choice(groq_keys)
    
    return ChatGroq(
        api_key=api_key,
        model=model,
        temperature=temperature,
        **kwargs
    )
