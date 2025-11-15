from openai import OpenAI
import openai  # just to print version

print("openai version:", openai.__version__)

client = OpenAI()  # uses OPENAI_API_KEY from env

response = client.responses.create(
    model="gpt-5",  # or gpt-5.1-thinking / gpt-5.1-instant if you prefer
    input="Write a one-sentence bedtime story about a unicorn."
)

print("response.output_text:")
print(response.output_text)
