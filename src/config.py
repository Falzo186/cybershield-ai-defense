import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_DEFENSOR = os.getenv("MODEL_DEFENSOR", "llama3.2:3b")
MODEL_ATACANTE = os.getenv("MODEL_ATACANTE", "llama3.2:3b")
MAX_RONDAS = 8
SECRETO = "FLAG{ejemplo123}"
TEMPERATURA_ATACANTE = 0.9
