import json
from llama_cpp import Llama
import logging

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO
)
# repo_id="TheBloke/Mistral-7B-v0.1-GGUF",
# filename="mistral-7b-v0.1.Q4_K_S.gguf",
# repo_id="TheBloke/Llama-2-7B-Chat-GGUF",
# filename="llama-2-7b-chat.Q8_0.gguf",
repo_id="SanctumAI/Meta-Llama-3-8B-Instruct-GGUF"
filename="meta-llama-3-8b-instruct.Q5_K_S.gguf"

# llm = Llama(model_path="llm/llama-2-7b-chat.Q4_K_S.gguf", verbose=False)
llm = Llama.from_pretrained(
    repo_id=repo_id,
    filename=filename,
    verbose=False
)

job_context = "Senior Data Engineer with 8 years of work experience"

fields_of_interest = [
    "city",
    "country",
    "currency",
    "job",
    "average_monthly_gross_salary",
    "net_to_gross_salary_ratio"
]

list_of_cities = [
    "Munich",
    "Berlin",
    "New York",
    "London",
    "Bangkok",
    "Madrid",
    "Milan"
]

for city in list_of_cities:
    prompt = f"""Provide a dictionary with the specified information for the city of { city }.
    The answer should be purely a JSON Array where each city is it's own object with { ', '.join(fields_of_interest)} as keys.
    For the salary consider the average monthly gross salary for a {job_context}.
    """

    logging.info("Prompt generated:\n")
    print(prompt)
    logging.info("Requesting response from LLM...")

    resp = llm(
        prompt,
        temperature=0.0,
        max_tokens=500000
        )

    logging.info("Response received:\n")

    resp_payload = resp["choices"][0]["text"]
    file_path = "llm/outputs.json"

    # Check if the file exists
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    # Append the outputs to the existing data
    data.append(resp_payload)

    # Write the updated data to the file
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)

    logging.info(f"{city} done.")