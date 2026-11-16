import anthropic
import os

from torchgen import model


# Aapki key yahan check hogi
client = anthropic.Anthropic(
    api_key="***REMOVED***" 
)


try:
    message = client.messages.create(
        # 2026 ka current professional model:
        model="claude-sonnet-4-6", 
        max_tokens=100,
        system="You are a helpful assistant.",
        messages=[
            {"role": "user", "content": "Confirm if I have access to Claude Sonnet 4.6."}
        ]
    )
    print("Success! You have access to Claude Sonnet 4.6.")
    print("Response:", message.content[0].text)

except anthropic.APIStatusError as e:
    if e.status_code == 403:
        print("Error 403: Aapka free tier is model ko support nahi karta. $5 deposit karein.")
    elif e.status_code == 404:
        print(f"Error 404: Model name '{model}' is still not found. Try 'claude-haiku-4-5'.")
    else:
        print(f"Error ({e.status_code}): {e.message}")
        