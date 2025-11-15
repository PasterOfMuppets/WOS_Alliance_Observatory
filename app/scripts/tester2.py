from openai import OpenAI

# TEMP: paste your new key here just to test.
# Remove it from the file after confirming it works.
client = OpenAI(api_key="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")

response = client.responses.create(
    model="gpt-5",
    input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)