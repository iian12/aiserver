import logging
from langchain_community.llms import Ollama


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_llama3_model():
    llm = Ollama(model="llama3:latest")
    return llm


model = load_llama3_model()
