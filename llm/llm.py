import transformers
import torch
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser


import os
from dotenv import load_dotenv

load_dotenv()

# HF_TOKEN = os.environ.get("HF_TOKEN")


# model_id="meta-llama/Meta-Llama-3-8B"
# model_id="01-ai/Yi-34B"
# model_id="bartowski/Meta-Llama-3-8B-Instruct-GGUF"
model_id = "google/gemma-2b"
# model_id = "mistralai/Mixtral-8x7B-v0.1"

print(1)

model = HuggingFaceEndpoint(
    repo_id=model_id,
    task="text-generation",
    model_kwargs={"max_length": 240},
    temperature=0.1,
    huggingfacehub_api_token=os.environ.get("HF_TOKEN"),
    repetition_penalty=5,
)

city = "Berlin"
job = "Senior Data Engineer with 7 years of work experience"

prompt_input = f"""Return the specified information for the for the city of {city}.
    The answer should contain the keys "city", "currency", "job", "average_monthly_gross_salary".
    Please answer for a {job}."""


# example_prompt = PromptTemplate(
#     input_variables=["question", "answer"], template="Question: {question}\n{answer}"
# )

# parser = JsonOutputParser()
# prompt = PromptTemplate(
#     template=prompt_input,
#     input_variables=["city", "job"],
#     # partial_variables={"format_instructions": parser.get_format_instructions()},
# )


# chain = prompt | model | parser

# response = chain.invoke(
#     {
#         "job": "Senior Data Engineer with 7 years of work experience",
#         "city": "Berlin",
#     }
# )

response = model.invoke(prompt_input)

print(response)
print(type(response))
