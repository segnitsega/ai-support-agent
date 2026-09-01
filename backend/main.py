from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()


if __name__ == "__main__":
    llm = init_chat_model("google_genai:gemini-3.5-flash")
    response = llm.invoke("Hello, who are you?")
    print(response)
