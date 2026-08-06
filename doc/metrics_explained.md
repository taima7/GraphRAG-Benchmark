# Evaluation Metrics Explained

This document explains, at the algorithm level, what every metric in
[`Evaluation/metrics/`](../Evaluation/metrics) actually computes. The metrics are grouped into the
three families of the benchmark pipeline: [indexing](#indexing-metrics) (judges the knowledge
graph), [retrieval](#retrieval-metrics) (judges the retriever) and
[generation](#generation-metrics) (judges the produced answer).

## Phases of the evaluation

Two things run: the **framework under test**, which produces artifacts, and the **evaluation**, which
reads those artifacts afterwards. The evaluation is entirely offline — no metric ever calls the
framework.

| Phase | The framework under test does | The evaluation reads | Script | Metrics applied |
| --- | --- | --- | --- | --- |
| **0. Benchmark inputs** | nothing yet | — | — | none |
| **1. Indexing** | reads the corpus, extracts entities and relationships, writes a graph | the graph files, via `--base_path` | [`indexing_eval.py`](../Evaluation/indexing_eval.py) | graph statistics |
| **2. Retrieval** | for each question, retrieves passages and records them as `context` | the prediction file, via `--data_file` | [`retrieval_eval.py`](../Evaluation/retrieval_eval.py) | Context Relevance, Evidence Recall |
| **3. Generation** | feeds the retrieved contexts to its LLM, records `generated_answer` | the same prediction file | [`generation_eval.py`](../Evaluation/generation_eval.py) | chosen per question type — see [the mapping below](#mapping-of-metrics-to-question-types) |

Phase 0 is what the benchmark ships: the corpus, plus a question set in which every item carries
`question`, `answer` (the ground truth answer), `evidence` and `question_type`.

**How often each phase is measured:**
- Indexing metrics run once per framework and dataset. No question is involved at all.
- Retrieval metrics run on every question of every question type. `retrieval_eval.py` groups the
  results by `question_type`, but the set of metrics never varies.
- Generation metrics run on every question, but which metrics apply depends on the question type.

**Phases 2 and 3 are one artifact read by two scripts.** The framework runs once and writes a
single prediction file holding both `context` and `generated_answer`; `retrieval_eval.py` and
`generation_eval.py` are independent passes over that same file and can be run alone, in either
order.

**Faithfulness sits across the phase 2/3 boundary.** It is filed as a generation metric and reads
the generated answer, but it compares against the retrieved contexts — the output of phase 2. That
is what makes it able to isolate blame: if Evidence Recall is high while Faithfulness is low, the
retriever found the evidence and the generator ignored it. Every other generation metric compares
against the ground truth answer, and so cannot tell those two failures apart.

## Terminology

Every metric below is described with the same **Input** / **Output** convention, each on its own
line. The input names are fixed and always refer to the objects in this table, regardless of what
the source code happens to call them locally.

| Term used in this document | Field in the data files | Parameter name(s) in the code | What it is |
| --- | --- | --- | --- |
| **question** | `question` | `question` | the question put to the framework |
| **ground truth answer** | `answer` in the question set, `ground_truth` in the prediction file | `ground_truth`, `reference` | the expected answer, shipped with the benchmark |
| **generated answer** | `generated_answer` | `answer`, `response` | what the framework under test produced |
| **retrieved contexts** | `context` | `contexts` | the passages the retriever returned for the question |
| **reference evidence** | `evidence` | `reference_evidence`, `evidence` | the corpus snippets that support the ground truth answer |

**"Reference answer" and "ground truth reference" are the same string.** It is the `answer` field
of the question set, copied into the prediction file as `ground_truth`. The code names it
inconsistently — [`compute_rouge_score`](../Evaluation/metrics/rouge.py) takes it as
`ground_truth`, [`compute_coverage_score`](../Evaluation/metrics/coverage.py) takes it as
`reference` — but [`generation_eval.py`](../Evaluation/generation_eval.py) passes the same value to
both. This document calls it the **ground truth answer** throughout.

It must not be confused with the **reference evidence** (`evidence`), a separate field holding the
corpus snippets that support that answer. Only the retrieval metrics use it.

## Mapping of metrics to question types

Which metrics run is decided per question type, by `metric_config` in
[`generation_eval.py`](../Evaluation/generation_eval.py):

| Question type | Metrics applied |
| --- | --- |
| Fact Retrieval | ROUGE-L, Answer Correctness |
| Complex Reasoning | ROUGE-L, Answer Correctness |
| Contextual Summarize | Answer Correctness, Coverage |
| Creative Generation | Answer Correctness, Coverage, Faithfulness |

The retrieval metrics (Context Relevance, Evidence Recall) run on every question type, and the
indexing metrics do not depend on questions at all.

## Generation Metrics

**At a glance:**

| Metric | In one line | Type | Divides by |
| --- | --- | --- | --- |
| **ROUGE-L** | length of the longest word sequence shared with the ground truth answer, turned into an F1 | deterministic | both answer lengths |
| **Coverage** | share of the ground truth answer's facts that the generated answer also states | LLM | ground truth facts (recall) |
| **Faithfulness** | share of the generated answer's statements that the retrieved contexts support | LLM | answer statements (precision) |
| **Answer Correctness** | statement-level F1 against the ground truth answer (75%) plus embedding similarity (25%) | LLM + embedding | both directions |

### ROUGE-L

**Type:** deterministic (pure math, no LLM judgment)

**Input:** generated answer, ground truth answer

**Output:** one number between 0.0 and 1.0

**How it works:**
1. Normalize both texts — stemming reduces words to roots (running → run).
2. Find the LCS: the longest sequence of words appearing in both texts in the same order, gaps allowed.
3. Precision = LCS length ÷ generated answer length.
4. Recall = LCS length ÷ ground truth answer length.
5. F1 = 2·P·R / (P + R) — harmonic mean, punishes imbalance between the two.

**Worked example:**
A generated answer is 20 words, the ground truth answer is 10 words, the LCS is 6. What are P, R, and F?

P = 6/20 = 0.3 (divided by the generated answer length),
R = 6/10 = 0.6 (divided by the ground truth answer length),
F = (2 × 0.3 × 0.6) / (0.3 + 0.6) = 0.36 / 0.9 = 0.4

**What the score means:**
- high (1.0) = the generated answer closely follows the ground truth answer —
most of the ground truth answer's words appear in it, in the same order, without much extra padding.
- low (0.0) = little shared word sequence —
the answer either missed the ground truth content, or used completely different wording.

**Limitation:**
ROUGE-L is used only for Fact Retrieval and Complex Reasoning question types, not for creative generation. For factual questions,
 answers are short and constrained ("Napoleon died in 1821") , there aren't many valid ways to phrase them, 
so word overlap with the ground truth answer actually correlates well with correctness. 
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

#### Demonstration (actual run)

Script: [`doc/demo_rouge.py`](demo_rouge.py) — example data:
[`doc/examples/rouge_example.json`](examples/rouge_example.json)

```shell
python doc/demo_rouge.py
```

It needs only `rouge_score` installed, not the full evaluation dependencies.

Ground truth answer (10 words):
"The sun is powered by nuclear fusion in its core."

Generated answer (14 words):
"The sun produces energy by nuclear fusion happening in the core of the sun."

Output:

```
    precision: 0.5000
       recall: 0.7000
     fmeasure: 0.5833
```

The LCS is 7 words (the, sun, by, nuclear, fusion, in, core). 
Recall = 7/10 = 0.7 because the denominator is the ground truth answer. 
Precision = 7/14 = 0.5 because the denominator is the generated answer, 
which is longer. F = 2·P·R/(P+R) = 0.5833.

This confirms the rule: the extra words in the answer lower precision while recall stays high.

### Coverage

**Type:** LLM-based (non-deterministic)

**Input:** question, ground truth answer, generated answer, and an LLM

**Output:** one number between 0.0 and 1.0

**How it works:**
1. The LLM receives the ground truth answer and is asked to split it into separate factual statements.
2. The LLM then receives those facts plus the generated answer, and marks each fact with 1 if it is covered in the generated answer, or 0 if it is not.
3. Score = sum of the 1s and 0s ÷ total number of facts extracted from the ground truth answer.

**Example (from the code):**
Ground truth answer about seasons → 2 facts extracted. The generated answer "Seasons are caused by Earth's tilted axis" covers 1 of them → score = 1/2 = 0.5

**Edge cases:**
- Empty ground truth answer → returns 1.0 (there are no facts to cover, so nothing is missing)
- LLM fails to return valid JSON after retries → returns NaN, which means the evaluation failed (not a bad score)

**What the score means:**
- high = the generated answer covers most of the facts from the reference
- low = the generated answer misses most of the reference facts

**Limitation:** it depends on an LLM, so it costs money and can give a slightly different score on different runs.

**Compared to ROUGE-L:** more expensive and slower, but it compares meaning instead of literal words — an answer using different wording can still score high.

### Faithfulness

**Type:** LLM-based (non-deterministic)

**Input:** question, generated answer, retrieved contexts, and an LLM

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

### Answer Correctness

**Type:** LLM-based (non-deterministic) + embedding-based

**Input:** question, generated answer, ground truth answer, an LLM, and an embedding model

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

```python
cosine_sim = np.dot(a_embed, gt_embed) / (np.linalg.norm(a_embed) * np.linalg.norm(gt_embed))
return (cosine_sim + 1) / 2
```

- Embed both texts → two vectors
- Dot product of the two vectors, divided by the product of their lengths (np.linalg.norm = vector length) — this is the cosine of the angle between them
- Cosine ranges from -1 (opposite) to 1 (identical direction); (cos + 1) / 2 rescales it to [0, 1]

## Retrieval Metrics

**At a glance:**

| Metric | In one line | Type | Divides by |
| --- | --- | --- | --- |
| **Context Relevance** | how well the retrieved contexts can answer the question, rated 0–2 by an LLM twice and averaged | LLM | number of ratings |
| **Evidence Recall** | share of the reference evidence items that the retrieved contexts contain | LLM | reference evidence items |

### Context Relevance

**Type:** LLM-based (non-deterministic)

**Family:** retrieval metric — it judges the retriever, not the generated answer

**Note:** Two implementations exist. `retrieval_eval.py` calls the three-argument version (v1), so v1 is what actually runs.
 v2 is imported in `__init__.py` under the alias `compute_context_relevance_v2` but no evaluation script calls it.

#### v1 (used)

**Input:** question, retrieved contexts, and an LLM

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

#### v2 (present, not used)

Differences from v1:
1. Takes the ground-truth **evidence** as an extra input, and judges relevance against the question *and* that evidence — a stricter, better-grounded test.
2. Splits long contexts into 3,000-character chunks and scores each, instead of truncating and discarding the rest.
3. Scores each context separately and averages, instead of joining all contexts into one block.
4. Requires a `reason` with each score, which tends to make LLM judgments more consistent.

### Evidence Recall

**Type:** LLM-based (non-deterministic)

**Family:** retrieval metric — it judges the retriever

**Input:** question, retrieved contexts, reference evidence, and an LLM

**Output:** one number between 0.0 and 1.0

**How it works:**
1. Unlike coverage, nothing needs to be split, because the reference evidence and the retrieved contexts are already lists.
2. The LLM receives the reference evidence and the retrieved contexts,
marks each evidence item with 1 if it can be attributed to the retrieved contexts.
It also gives a reason for each decision (one sentence), like faithfulness and answer correctness do.
3. Score = sum of attributed evidence items ÷ number of reference evidence items

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
while evidence recall divides by the number of reference evidence items (judging the coverage of the facts).

## Indexing Metrics

**At a glance:**

| Metric | In one line | Type | Output |
| --- | --- | --- | --- |
| **Graph statistics** | ~20 structural numbers describing the knowledge graph itself — size, connectivity, fragmentation, clustering | deterministic | a dictionary, not a 0–1 score |

**Type:** deterministic (pure graph statistics — no LLM, no question, no ground truth)

**Family:** indexing — judges the knowledge graph itself, before any question is asked

**Input:** the graph files produced by a framework during indexing

**Output:** a dictionary of ~20 numbers (not a 0–1 score)

**How it works:**
1. Load the graph. Each framework stores it differently: 
Microsoft GraphRAG uses two parquet files (entities and relationships), 
LightRAG uses GraphML, Fast-GraphRAG uses picklez, HippoRAG2 uses pickle.
 All of them are converted into a common `igraph.Graph` object.
2. `analyze_graph()` computes the statistics on that graph.
3. If several graphs are found under the given path, every statistic is averaged across them.

**The statistics, grouped:**
- **Size:** num_nodes, num_edges -how many entities and relationships the framework extracted
- **Connectivity:** average_degree (edges per node), density (actual edges out of all possible ones), diameter (longest shortest path; returns infinity when the graph is disconnected)
- **Fragmentation:** num_components (how many disconnected pieces), largest_component_size, num_isolated_nodes (entities with no relationship at all), plus five different averages of component size
- **Clustering:** average_clustering_coefficient -how often a node's neighbours are also connected to each other
- **Degree distribution:** num_nodes_degree_above_1 / _2 / _3 — 
how many entities have more than 1, 2 or 3 connections

**Why five averages of component size?** Component sizes are usually very skewed -
one giant component plus many small ones. A plain mean hides that, so the code also reports median, 
trimmed mean (dropping the largest and smallest), geometric mean and harmonic mean; 
each is affected differently by outliers.

**How to interpret:** these numbers are not "higher is better" on their own. 
They are descriptive, and only become meaningful when the same statistics are compared across frameworks on the same dataset. 
A heavily fragmented graph with many isolated nodes suggests entity extraction produced disconnected facts, 
which limits what graph traversal can reach during retrieval.

**Limitation:** it measures structure, not correctness. 
A graph can be dense and well connected while containing wrong entities or hallucinated relationships — nothing here checks whether the extracted content is accurate.
