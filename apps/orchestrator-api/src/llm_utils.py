import os
from langchain_groq import ChatGroq

def get_chat_groq(model: str = "qwen/qwen3-32b", temperature: float = 0.1, **kwargs) -> ChatGroq:
    """Initialize a ChatGroq model using API key from the environment."""

    
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model=model,
        temperature=temperature,
        **kwargs
    )
