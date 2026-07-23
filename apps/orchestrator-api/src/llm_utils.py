import os
from langchain_groq import ChatGroq

# Model Configurations
SUPERVISOR_MODEL = "openai/gpt-oss-120b"
QUANTITATIVE_MODEL = "openai/gpt-oss-120b"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

def get_chat_model(model: str = DEFAULT_MODEL, temperature: float = 0.1, **kwargs) -> ChatGroq:
    """Initialize a ChatGroq model using API key from the environment."""

    api_key = os.getenv("GROQ_API_KEY_4")
    if not api_key:
        raise ValueError("No GROQ_API_KEY_4 found in environment variables.")
    
    return ChatGroq(
        api_key=api_key,
        model=model,
        temperature=temperature,
        **kwargs
    )
