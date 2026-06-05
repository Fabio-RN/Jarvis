from groq import Groq
from core.config import GROQ_API_KEY
 
client = Groq(api_key=GROQ_API_KEY)
MODELO = "llama-3.3-70b-versatile"