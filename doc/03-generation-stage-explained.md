# Generation Stage — Explained

## What is generation?

Generation is the last step. It takes the **retrieved context** (the text pulled out in the retrieval stage — see [02-retrieval-stage-explained.md](./02-retrieval-stage-explained.md)) and the original **question**, hands both to an LLM, and asks it to write the final answer.

One important thing worth noticing: unlike indexing and retrieval, **generation itself doesn't really differ between frameworks**. By the time you reach this stage, all you have is "some context text" plus "a question" — GraphRAG, LightRAG, Fast-GraphRAG, and HippoRAG2 could all hand this off to the exact same LLM in the exact same way. The real differences between frameworks live **upstream**, in *what* context they hand over (covered in the retrieval doc), not in *how* the final answer gets written. So generation metrics end up measuring two things at once: how well the LLM wrote the answer, **and** indirectly, how good the context it was given actually was.

## The four generation metrics

### 1. ROUGE-L (deterministic — no LLM involved)

Looks for the **longest common sequence of words** shared between the generated answer and the reference (ground-truth) answer, then turns that overlap into an F1 score (a precision/recall-style combined score).

**Its big weakness:** it only looks at matching *words*, not *meaning*. If the reference says "Ahmad is employed by Company X" and the generated answer says "Ahmad works for Company X" — same meaning, different words — ROUGE-L scores this low, even though the answer is completely correct. This is called **semantic blindness**.

### 2. Coverage (LLM-based)

An LLM extracts individual **facts** from the reference answer, then checks how many of those facts actually show up in the generated answer.

This only measures **recall** — completeness. It tells you if anything important got left out, but it does **not** penalize the generated answer for adding **extra, wrong** information. A generated answer that includes every correct fact *plus* several made-up ones would still score well on Coverage.

### 3. Faithfulness (LLM-based)

The generated answer gets split into individual statements, and each one is checked **against the retrieved context** — not against the reference/ground-truth answer.

This is deliberate, and it's the key design choice of this metric: Faithfulness isolates **hallucination** — did the LLM say something that wasn't actually supported by what it was given? Because it compares against the *retrieved context* rather than ground truth, an answer can score perfectly on Faithfulness while still being **factually wrong overall** — if the retrieved context itself was incomplete or wrong, the LLM can be 100% faithful to bad information. That's not a generation problem; that's a retrieval problem, and it's exactly why Faithfulness and the retrieval metrics (Context Relevance, Evidence Recall) are kept separate (see the retrieval doc's section on why scoring stages separately matters).

### 4. Answer Correctness (LLM + embeddings, hybrid)

Each statement in the generated answer gets classified against the reference answer as:
- **True Positive** — correct fact, present in both.
- **False Positive** — stated in the generated answer, but not actually in the reference (extra/wrong info).
- **False Negative** — in the reference, but missing from the generated answer.

This produces a precision/recall-style score, which makes up **75%** of the final score. The remaining **25%** comes from **semantic similarity** — comparing the generated and reference answers as embeddings, to also capture overall meaning-match beyond exact fact-by-fact classification.

This is the most complete of the four metrics: it catches missing facts (like Coverage), catches *extra wrong* facts (which Coverage doesn't), and also rewards answers that are worded differently but mean the same thing (which raw fact-classification alone wouldn't fully capture).

## What each metric actually isolates

| Metric | Compares generated answer against | What it catches | What it misses |
|---|---|---|---|
| **ROUGE-L** | Reference answer (word overlap) | Exact wording match, free/instant | Correct answers phrased differently |
| **Coverage** | Reference answer (facts) | Missing information (recall only) | Extra/wrong information added |
| **Faithfulness** | Retrieved context (not reference!) | Hallucination — ungrounded claims | Whether the context itself was any good |
| **Answer Correctness** | Reference answer (facts + meaning) | Missing info, extra wrong info, and meaning — most complete | Nothing major; it's the most holistic, but also the most expensive |

## Why is ROUGE-L still useful, despite being "semantically blind"?

This is worth answering directly, since it's a fair question: if ROUGE-L can't tell a correct paraphrase from a wrong answer, why keep it around at all?

1. **It's free and instant.** No LLM call, no cost, no waiting, and no randomness — the same input always produces the exact same score. The other three metrics all cost money and take time because they call an LLM.
2. **It's actually not bad for short, factual answers.** When the correct answer is something like a name, a date, or a number, there usually isn't much room for paraphrasing — "2024" doesn't have many alternate ways to be written. For that narrow but common question type, word-overlap is a reasonable cheap proxy for correctness.
3. **It's a fast sanity check during iteration.** While experimenting or debugging a pipeline (trying different chunk sizes, different retrieval settings, etc.), running the expensive LLM-based metrics on every single test run is slow and costly. ROUGE-L can catch big, obvious regressions instantly, so it's practical to run constantly, saving the expensive LLM-based metrics for final validation runs.
4. **It fails in a *different* way than the LLM-based metrics do — and that's actually valuable.** Coverage, Faithfulness, and Answer Correctness are all judged *by an LLM*, which means they can inherit that LLM's own biases or blind spots. ROUGE-L doesn't depend on any LLM's judgment at all, so it gives an independent, differently-flawed signal — useful specifically *because* its weaknesses don't overlap with the other metrics' weaknesses.

So the honest framing: ROUGE-L is a weak metric on its own, but a genuinely useful **cheap, fast, independent check** alongside the richer LLM-based metrics — not a replacement for them.

---

This completes all three stages: [Indexing](./01-indexing-stage-explained.md) → [Retrieval](./02-retrieval-stage-explained.md) → Generation.
