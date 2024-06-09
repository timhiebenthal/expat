install_requirements:
	pip install -r requirements.txt

dbt_run:
	cd dbt && dbt run

load_data:
	cd loading && python cities.py && python forex.py && python costofliving.py

streamlit:
	streamlit run data_viz/app.py

pull_llama:
	cd local_llm/ && curl --max-time 900 -O https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_S.gguf?download=true