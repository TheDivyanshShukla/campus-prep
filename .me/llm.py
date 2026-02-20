from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import httpx
from dotenv import load_dotenv
import os
load_dotenv()

# Configure client to use Bifrost
llm = ChatOpenAI(
    model="gemini/gemini-2.5-flash",
    # model="openai/gpt-4o-mini",
    openai_api_base="https://bifrost.naravirtual.in/langchain",
    openai_api_key="dummy-key",
    default_headers={"Authorization": f"Basic {os.getenv('BIFROST_API_KEY')}"},
)

response = llm.invoke([HumanMessage(content="Hello!")])
print(response.content)
