# GraphRAG-Benchmark — Evaluation Metrics Explained

## ROUGE-L

**Type:** deterministic (pure math, no LLM judgment)

**Input:** generated answer (string), ground truth reference (string)
**Output:** one number between 0.0 and 1.0

**How it works:**
1. Normalize both texts — stemming reduces words to roots (running → run).
2. Find the LCS: the longest sequence of words appearing in both texts in the same order, gaps allowed.
3. Precision = LCS length ÷ generated answer length.
4. Recall = LCS length ÷ ground truth length.
5. F1 = 2·P·R / (P + R) — harmonic mean, punishes imbalance between the two.

**Worked example:**
A model's answer is 20 words, the GT is 10 words, the LCS is 6. What are P, R, and F?
P= 6/10, R= 6/20 , f =(2*0.6* 0.3)/(0.9)

**What the score means:**
- high (1.0)= the generated answer closely follows the reference
 most of the reference's words appear in it, in the same order, without much extra padding.
- low (0.0)= little shared word sequence 
the answer either missed the reference content, or used completely different wording.
- Limitation: 
ROUGE-L is used only for Fact Retrieval and Complex Reasoning question types, not for creative generation. For factual questions,
 answers are short and constrained ("Napoleon died in 1821") , there aren't many valid ways to phrase them, 
so word overlap with the reference actually correlates well with correctness. 
And ROUGE-L specifically beats simpler word-counting (ROUGE-1) because requiring the right order catches scrambled or incoherent answers.
ROUGE-L is semantically blind: an answer phrased entirely in synonyms ("the feline rested on the rug" vs "the cat sat on the mat")
 can be fully correct yet score near zero.
its properties, not its intelligence. It's the only metric in this pipeline that is deterministic, free, instant, and reproducible ,
 same inputs, same score, forever. 
Every other metric here asks an LLM to judge, which costs money and can give a different score tomorrow. 
So ROUGE-L serves as the stable, cheap sanity baseline,
 and the benchmark pairs it with Answer Correctness (LLM-based) precisely to cover its semantic blindness.
 Each metric compensates for the other's weakness.
 That's why the benchmark applies it only to short factual question types and pairs it with LLM-based metrics like Answer Correctness