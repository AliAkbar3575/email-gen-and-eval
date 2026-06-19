### How to run the project
---

go to visual studio code terminal and run:

```git clone https://github.com/AliAkbar3575/email-gen-and-eval```

Then go to the project root directory and run:

```
conda create -n new_env
conda activate new_env
```
Then create a ```.env``` file and put the key, which is provided in the last page of final_assessment_report.pdf (attached in the email). After putting the file, run the following commands:
```
pip install -r requirements.txt
uvicorn api.routes:app --reload
streamlit run main.py
```

<img width="961" height="545" alt="Screenshot from 2026-06-19 08-25-58" src="https://github.com/user-attachments/assets/9d8eb152-d8ab-46b9-91d2-5d5be4162ecc" />

Then provide ```user request``` and select ```model``` and click ```generate email```
Then this will appear:

<img width="949" height="716" alt="Screenshot from 2026-06-19 08-26-23" src="https://github.com/user-attachments/assets/7ff63b77-6c4c-41dd-b641-b692080d2fac" />

Then click the button ```evaluate LLM``` to see the evaluation.

<img width="942" height="660" alt="Screenshot from 2026-06-19 08-27-10" src="https://github.com/user-attachments/assets/af1a0b04-9150-4402-9376-69c81864a5db" />

The output will be generated in the ```outputs``` folder (2 .md files will be found).
