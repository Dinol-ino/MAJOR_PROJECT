# Dataset Evaluation Plan

## Project

**Project Title:** Defensive RAG for Legal Firms

---

## Objective

The objective of this phase is to evaluate the security and robustness of the Gemma 4 E2B model using benchmark datasets and legal-domain documents before integrating it into the Legal Retrieval-Augmented Generation (RAG) system.

---

## Datasets Used

### Dataset 1: Indian Supreme Court Judgments

**Purpose**

This dataset serves as the legal knowledge base for the Legal RAG system. It is used to evaluate document retrieval, legal summarization, citation consistency, and robustness against malicious instructions embedded within legal documents.

**Evaluation Goals**

- Legal document summarization
- Retrieval quality
- Context understanding
- Hallucination detection
- Fake citation detection
- Prompt injection resistance within legal documents

---

### Dataset 2: Security Benchmark Dataset

**Purpose**

This dataset contains adversarial prompts designed to evaluate the security of Large Language Models.

**Evaluation Goals**

- Prompt Injection
- Jailbreak Resistance
- Role Manipulation
- Data Exfiltration
- Context Override
- Hallucination Testing
- Prompt Leakage
- Safety Evaluation

---

## Evaluation Methodology

The evaluation will be performed in four stages:

1. Baseline Manual Security Testing
2. Benchmark Dataset Evaluation
3. Legal Document Security Evaluation
4. Comparative Analysis and Reporting

---

## Expected Deliverables

- Security evaluation report
- PASS / FAIL analysis
- Attack-wise performance summary
- Security observations
- Recommendations for secure Legal RAG deployment

---

## Current Status

| Task | Status |
|------|--------|
| Baseline Manual Testing | Completed |
| Security Benchmark Dataset | Planned |
| Indian Supreme Court Dataset Evaluation | Planned |
| Malicious Legal Document Testing | Planned |
| Final Analysis | Planned |

---

## Conclusion

The dataset evaluation phase extends the baseline manual testing by assessing the model against standardized benchmark attacks and real-world legal documents. The combined evaluation will provide a comprehensive understanding of the model's security, robustness, and suitability for deployment within a Defensive Legal RAG system.