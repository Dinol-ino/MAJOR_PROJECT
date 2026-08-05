# Dataset Evaluation Report

## Project Title
Defensive RAG for Legal Firms

## Objective

To evaluate the security of the locally deployed Gemma 4 E2B language model before integrating it into the Legal Retrieval-Augmented Generation (RAG) system.

---

## Model Information

- **Model:** Gemma 4 E2B
- **Platform:** LM Studio
- **API:** Local OpenAI-compatible API

---

## Dataset

The evaluation dataset contains prompts covering the following attack categories:

- Prompt Injection
- Jailbreak
- Hallucination
- Data Exfiltration
- Role Manipulation

Each prompt specifies an expected secure behaviour.

---

## Evaluation Methodology

1. Load prompts from `security_prompts.csv`.
2. Send each prompt to the local model.
3. Capture the generated response.
4. Compare the response with the expected behaviour.
5. Store the results in `evaluation_results.csv`.
6. Calculate overall security metrics.

---

## Evaluation Metrics

| Metric | Result |
|---------|---------|
| Total Attacks | 5 |
| PASS | 4 |
| FAIL | 1 |
| REVIEW | 0 |
| Security Score | 80% |

---

## Conclusion

The automated security evaluation pipeline successfully assessed the Gemma 4 E2B model against representative security attack prompts. The model achieved an overall security score of **80%**, demonstrating strong resistance to common prompt injection and jailbreak attacks while identifying one scenario for future improvement. The evaluation framework is reusable and can be extended with larger benchmark datasets and additional local language models.