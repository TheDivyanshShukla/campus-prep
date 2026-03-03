import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY", "4vL3yiLuPsnEgb43g5gLpO1lV04UjPQgyZdwEyMTrNsYbSFOVnBBJQQJ99CCACqBBLyXJ3w3AAAAACOGdAYF"),
    base_url="https://testjk-gwa-agw.openai.azure.com/openai/v1/",
)

completion = client.chat.completions.create(
  model="gpt-4.1-mini", # Replace with your model deployment name.
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "When was Microsoft founded?"}
  ]
)

#print(completion.choices[0].message)
print(completion.model_dump_json(indent=2))