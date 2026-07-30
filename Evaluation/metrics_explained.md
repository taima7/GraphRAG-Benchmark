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

## Coverage

**Type:** LLM-based (non-deterministic)

**Input:** question, reference answer, generated answer, and an LLM
**Output:** one number between 0.0 and 1.0

**How it works:**
1. The LLM receives the reference answer and is asked to split it into separate factual statements.
2. The LLM then receives those facts plus the generated answer, and marks each fact with 1 if it is covered in the generated answer, or 0 if it is not.
3. Score = sum of the 1s and 0s ÷ total number of facts extracted from the reference.

**Example (from the code):**
Reference about seasons → 2 facts extracted. The answer "Seasons are caused by Earth's tilted axis" covers 1 of them → score = 1/2 = 0.5

**Edge cases:**
- Empty reference → returns 1.0 (there are no facts to cover, so nothing is missing)
- LLM fails to return valid JSON after retries → returns NaN, which means the evaluation failed (not a bad score)

**What the score means:**
- high = the generated answer covers most of the facts from the reference
- low = the generated answer misses most of the reference facts

**Limitation:** it depends on an LLM, so it costs money and can give a slightly different score on different runs.

**Compared to ROUGE-L:** more expensive and slower, but it compares meaning instead of literal words — an answer using different wording can still score high.

## Faithfulness

**Type:** LLM-based (non-deterministic)

**Input:** question, answer, contexts, and an LLM
**Output:** one number between 0.0 and 1.0

**How it works:**
1. The LLM receives the answer and is asked to split it into separate statements (forbidden pronouns, so the statement can stand alone)
2. The LLM then receives those retrieved contexts plus the answer, 
and marks each statement with 1 if it is supported by the retrieved contexts, or 0 if it is not.
3. Score = sum of the 1s and 0s ÷ total number of statements.
**Note:** The evaluation prompt includes few-shot examples and asks the LLM to give a `reason` with each verdict, 
which makes the judgments more consistent.

**Example (from the code):**
Context: John studies Computer Science, is enrolled in Data Structures, Algorithms and Database Management,
 studies a lot and stays late in the library.
Statements from the answer: "John is majoring in Biology" (0), "John is taking a course on Artificial Intelligence" (0),
 "John is a dedicated student" (1), "John has a part-time job" (0).
Score = 1/4 = 0.25

**Edge cases:**
- Empty answer→ returns 1.0 (there are no statements so nothing is missing)
- LLM fails to return retrieved contexts → returns 0 which means the statements can't be supported
- Extraction/JSON failure → NaN

**What the score means:**
- high = most of the statements in the answer are supported and grounded by the retrieved contexts
- low = the model made claims the context doesn't support, i.e Hallucination

**Limitation:** it depends on an LLM, so it costs money and can give a slightly different score on different runs.
**Compared to Coverage:**
 Coverage and faithfulness use the same two-step LLM machinery and the same final line sum(...)/len(...).
 Coverage divides by the reference facts (recall -did the answer miss anything required?). 
Faithfulness divides by the answer's own statements (precision -did the answer invent anything unsupported?).



**Edge cases:**
- Empty answer→ returns 1.0 (there are no statements so nothing is missing)
- LLM fails to return retrieved contexts → returns 0 which means the statements can't be supported
- Extraction/JSON failure → NaN

**What the score means:**
- high = most of the statements in the answer are supported and grounded by the retrieved contexts
- low = the model made claims the context doesn't support, i.e Hallucination

**Limitation:** it depends on an LLM, so it costs money and can give a slightly different score on different runs.
**Compared to Coverage:**
 Coverage and faithfulness use the same two-step LLM machinery and the same final line sum(...)/len(...).
 Coverage divides by the reference facts (recall -did the answer miss anything required?). 
Faithfulness divides by the answer's own statements (precision -did the answer invent anything unsupported?).

## Answer Correctness

**Type:** LLM-based (non-deterministic) + embedding-based

**Input:** question, generated answer, ground truth, an LLM, and an embeddings model
**Output:** one number between 0.0 and 1.0

**How it works:**
1. The LLM splits **both** the generated answer and the ground truth into separate statements (no pronouns, so each statement stands alone). This is the only metric that splits both sides.
2. The LLM classifies every statement into one of three categories, with a reason:
   - **TP** — stated in the answer and supported by the ground truth
   - **FP** — stated in the answer but not supported by the ground truth
   - **FN** — present in the ground truth but missing from the answer
3. Factuality score = F1 from those counts:
   precision = TP / (TP + FP), recall = TP / (TP + FN), F1 = 2·P·R / (P + R)
4. Semantic similarity = cosine similarity between the embeddings of the answer and the ground truth, rescaled to [0, 1].
5. Final score = **0.75 × factuality + 0.25 × similarity**

**Note:** The prompt includes few-shot examples and requires a `reason` for each classification, 
which makes the judgments more consistent.

**Example (from the code):**
Question: "What powers the sun and what is its primary function?"
Answer: the sun runs on nuclear fission; its main function is to give light to the solar system.
Ground truth: five statements about fusion, energy release, heat and light for life, climate, 
and weather/ocean currents.

Classification:
- TP (1): "the sun provides light to the solar system" — partly supported by the ground truth
- FP (1): "the sun is powered by nuclear fission" — contradicts the ground truth, which says fusion
- FN (5): all five ground truth statements the answer never mentions

precision = 1/2 = 0.5, recall = 1/6 ≈ 0.17, F1 ≈ 0.25
Final score = 0.75 × 0.25 + 0.25 × (similarity)

**Edge cases:**
- Both statement lists empty → returns 1.0
- JSON parse failure → returns 0.0. Note this differs from coverage and faithfulness, 
which return NaN on failure; a 0 here looks like a bad answer rather than a failed measurement.

**What the score means:**
- high = the answer states what the ground truth requires and adds little that is unsupported
- low = the answer contradicts the ground truth, or misses most of it, or both

**Limitation:** depends on an LLM and an embedding model, 
so it costs money and the score can vary between runs.

**Compared to the others:** coverage measures only the recall direction, faithfulness only the precision direction. 
Answer correctness covers both at once (FP is the precision side, FN the recall side) and adds a similarity term on top.

**Semantic similarity (25% of the score):**
This part does not use the LLM. Both the generated answer and the ground truth are converted into vectors(of ~1024 numbers representing its meaning-Those numbers come out of a neural network )
 by an embedding model (bge-large-en-v1.5 in the evaluation script). 
The metric then computes the cosine of the angle between the two vectors, and rescales it from [-1, 1] to [0, 1] with (cos + 1) / 2.

Cosine measures direction, not distance, so two texts about the same topic score high even if one is much longer than the other.

This value cannot be computed by hand -it requires running the embedding model -so only the factuality part is calculated in the example above.
Cosine similarity in this metric isn't computed on the words; it's computed on embeddings: each text is passed to an embedding model (in the eval script, BAAI/bge-large-en-v1.5),
in python
cosine_sim = np.dot(a_embed, gt_embed) / (np.linalg.norm(a_embed) * np.linalg.norm(gt_embed))
return (cosine_sim + 1) / 2
Embed both texts → two vectors
Dot product of the two vectors, divided by the product of their lengths (np.linalg.norm = vector length) — this is the cosine of the angle between them
Cosine ranges from -1 (opposite) to 1 (identical direction); (cos + 1) / 2 rescales it to [0, 1]

## Context Relevance

**Type:** LLM-based (non-deterministic)
**Family:** retrieval metric — it judges the retriever, not the generated answer

**Note:** Two implementations exist. `retrieval_eval.py` calls the three-argument version (v1), so v1 is what actually runs.
 v2 is imported in `__init__.py` under the alias `compute_context_relevance_v2` but no evaluation script calls it.

### v1 (used)

**Input:** question, retrieved contexts, LLM
**Output:** one number between 0.0 and 1.0

**How it works:**
1. The LLM is asked to rate how well the context can answer the question on a 0–2 scale: 0 = no relevant information, 1 = partially relevant, 2 = fully relevant.
 The prompt requires strict JSON with a single "score" key and forbids any explanation.
2. The same prompt is sent twice, because a single LLM call can be inconsistent; two independent ratings reduce that variance.
3. Each rating is divided by 2 to rescale it to [0, 1].
4. Score = sum(scores) / len(scores) — the average of the valid ratings.

**Edge cases:**
- Empty question or empty contexts → 0.0 (nothing retrieved means nothing relevant)
- Context identical to, or contained in, the question → 0.0, because the retriever returned the question back instead of new information
- All LLM calls fail → NaN, meaning the evaluation failed rather than the retrieval being bad

**What the score means:**
- high = the retriever returned passages that can actually answer the question
- low = the retrieved passages are off-topic or insufficient

**Limitation:** depends on an LLM, so it costs money and can vary between runs.
 It also judges relevance to the question only — a context can look relevant without containing the specific evidence the correct answer needs.

### v2 (present, not used)

Differences from v1:
1. Takes the ground-truth **evidence** as an extra input, and judges relevance against the question *and* that evidence — a stricter, better-grounded test.
2. Splits long contexts into 3,000-character chunks and scores each, instead of truncating and discarding the rest.
3. Scores each context separately and averages, instead of joining all contexts into one block.
4. Requires a `reason` with each score, which tends to make LLM judgments more consistent.

## Evidence Recall

**Type:** LLM-based (non-deterministic)
**Family:** retrieval metric — it judges the retriever

**Input:** reference evidences, retrieved contexts
**Output:** one number between 0.0 and 1.0

**How it works:**
1. Unlike coverage, nothing needs to be split, because we already have list of reference evidences and retrived contexts
2. The LLM receives references evidences and retrieved contexts , 
marks each evidence item with 1 if it can be attributed to the retrieved contexts. 
It also gives a reason for each decision (one sentence), like faithfulness and answer correctness do.
3. Score = sum of attributed evidences ÷ number of reference evidences

**Example (from the prompt):**
Context: "Einstein won the Nobel Prize in 1921 for physics."
Evidence: "Einstein received the Nobel Prize" → 1 ; "He was born in Germany" → 0
Score = 0.5

**Edge cases:**
- Empty context →0.0 (nothing to attribute to - a real result)
- No valid classifications after retries → NaN  

**What the score means:**
- high = the retriever found most of the evidence the correct answer needs
- low = the retriever missed most of it(it is weak)

**Limitation:** depends on an LLM, so it costs money and can vary between runs. Also, long contexts are truncated at 20,000 characters — evidence appearing past that point is counted as not found. 
(The code carries a TODO for smarter truncation)

**Compared to Faithfulness:** both check against the retrieved contexts,
 but faithfulness divides by answer statements  (judging the hallucinations), 
while evidence recall divides by number of reference evidences (judging the coverage of the facts  ).
