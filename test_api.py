import os
from openai import AzureOpenAI

# Load API key
with open("API_KEYS") as f:
    for line in f:
        if line.startswith("AZURE_OPENAI_API_KEY"):
            api_key = line.split("=", 1)[1].strip()
            break

# Test the endpoint
client = AzureOpenAI(
    api_key=api_key,
    api_version="2024-02-15-preview",
    azure_endpoint="https://ovalnairr.openai.azure.com/"
)

try:
    # Try a simple completion
    response = client.chat.completions.create(
        model="gpt-4o",  # Your deployment name
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=10
    )
    print("✅ Endpoint is valid!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")