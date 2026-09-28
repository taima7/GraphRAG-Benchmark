# Retrieval Stage — Explained

## What is retrieval?

Indexing (see [01-indexing-stage-explained.md](./01-indexing-stage-explained.md)) is **offline** — it happens once, before any question exists, and builds one general-purpose graph containing everything in the document. Retrieval is the opposite: it's **online** — it runs fresh, every single time a question comes in.

Indexing has no way to know in advance which slice of the graph any future question will need — "relevant" is entirely defined by the specific question being asked. Retrieval's job is to take one specific question, search the graph indexing already built, and pull out the small piece that's actually relevant right now.

That pulled-out material is called the **retrieved context**. It's the input handed to the LLM in the next stage (generation) to write an answer.

## The shared starting point: seeds, then expand

Every framework turns the question into something comparable against the graph — usually via **embeddings** (question meaning vs. node meaning) or **keywords** (specific words matched against entity names/tags). This produces a small set of **seed nodes**: starting points in the graph.

Retrieval does not stop at direct similarity. Why: direct similarity only finds nodes that *look like* the question in wording. But some relevant nodes (like "Sara" in a question that never mentions her by name) are only relevant because they're **connected**, through a chain of edges, to something that does match directly. This is the same reason a graph was built in the first place (see indexing doc) — multi-hop reasoning has to actually get *executed* somewhere, and that's here: seeds are found by direct matching, then the graph's edges carry relevance to everything connected to those seeds.

---

## GraphRAG: Local Search vs. Global Search

GraphRAG has two main retrieval modes, chosen based on question type (newer versions also add DRIFT Search and Basic Search, not covered here):

- **Local Search** (specific questions): find seed entities via embedding similarity to the question, then pull in their **direct (1-hop)** related entities and relationships, their claims, their source text chunks, and the **community reports** of the communities those entities belong to.
- **Global Search** (broad, thematic questions): skips entities entirely. Searches across **community reports** (built during indexing) using a map-reduce process — check the question's relevance against each report, then combine the useful ones.

**Why the wrong mode fails:** Local Search on a broad question fails because a broad question doesn't resemble any single entity's description, and even if it picked seeds, it only expands to a narrow 1-hop neighborhood plus the few community reports linked to those seeds — not the whole dataset. Global Search on a specific question fails because community reports are compressed summaries; a precise detail may get flattened out of the summary entirely, and checking every report for one fact is expensive overkill.

## LightRAG: dual-level keyword retrieval

The question is split by an LLM into:
- **Low-level keywords** (specific things) → matched against the entity vector index.
- **High-level keywords** (general topics) → matched against the relationship-keyword vector index.

Then LightRAG also adds the **one-hop neighbors** of the matched entities and relationships, to bring in nearby connected facts.

In the paper, both levels run together on every question and the results are merged. The code also offers separate modes: `local` (low-level only), `global` (high-level only), `hybrid` (both), plus `naive` and `mix`. **This benchmark runs LightRAG in `hybrid` mode.**

**Possible gap vs. GraphRAG's Global Search:** the "high-level" side still only matches individual relationship-keyword tags — scattered facts that happen to share a keyword. It never produces a pre-written summary the way a community report does. **But note:** this is an argument from the design; the LightRAG paper's own tests on broad questions report that LightRAG beats GraphRAG.

## Fast-GraphRAG and HippoRAG2: Personalized PageRank (PPR)

Both use the same core trick, borrowed from PageRank (the original Google ranking algorithm): instead of ranking by "how many pages link here," **Personalized** PageRank injects a relevance "boost" at the seed nodes matched to the question, and lets that score **spread outward** through the graph's edges, fading with each hop.

**Why this beats Local Search on hard questions:** Local Search has a hard cutoff at 1 hop — anything further away is structurally unreachable, no matter how relevant. PPR has no hard cutoff; relevance keeps spreading across as many hops as the graph allows, just weaker with distance. So multi-hop questions (2, 3+ hops from a seed) can still surface, just ranked lower than closer facts.

**The difference between the two:**
- **Fast-GraphRAG**: first an LLM pulls the entities out of the question, and these are matched to graph entities by embedding similarity (the seeds). Its graph has no passage nodes, so PPR only ranks **entities**. Then two **separate steps afterward** turn that into text: each relationship gets a score from the scores of the entities it connects, and each chunk gets a score by adding up the scores of the relationships that were extracted from it. The top entities, relationships, and chunks become the context. The limit: chunks are never part of the PageRank itself — their scores are worked out afterward, from the entity scores.
- **HippoRAG2**: seeds are chosen differently. The whole question is matched against **triples** by embedding similarity, and then an LLM **filters** these triples, keeping only the relevant ones (the paper calls this "recognition memory"). The entities in the kept triples become seeds. **All passage nodes** are also seeds, each weighted by how similar it is to the question. Because passage nodes are already part of the graph (from indexing), PPR spreads relevance across entity nodes **and** passage nodes in the *same* pass. Passages are then ranked by their PageRank score, and the top passages become the context — so a passage's score already reflects graph-connectivity to the question, with no separate "go find the source chunk" step.

---

## What "retrieved context" actually is

Regardless of framework or mechanism, retrieval's output is always **text**: some combination of original passages, entity descriptions, relationship descriptions, claims (GraphRAG), or community report text (GraphRAG Global Search), bundled together. This bundle is handed directly to the LLM in the generation stage.

This is also why `metrics_explained.md` notes that *"Phases 2 and 3 are one artifact read by two scripts"* — one prediction file holds both the retrieved context and the generated answer per question, which is what allows retrieval quality and generation quality to be scored **independently**.

**Why scoring them separately matters:** a single combined "was the final answer correct?" score can't tell you *where* a failure happened. Two very different problems look identical from the outside:
1. **Retrieval failure** — the graph/search never found the relevant facts; the LLM never saw the right information.
2. **Generation failure** — retrieval found the right context, but the LLM ignored it, misread it, or hallucinated anyway.

Separate metrics pinpoint which half of the pipeline to actually fix: **Context Relevance / Evidence Recall** isolate retrieval quality; **Faithfulness / Answer Correctness** isolate generation quality, given whatever context retrieval provided.

---

## Comparison table

| Framework | Retrieval mechanism | Good for | Weak for |
|---|---|---|---|
| **GraphRAG** | Local Search (1-hop from seed entities) or Global Search (community reports, map-reduce) — picks one mode | Specific questions (Local) or broad thematic questions (Global) — whichever mode matches | Wrong mode picked for the question type; Local Search structurally can't reach beyond 1 hop |
| **LightRAG** | Dual-level: low-level keywords → entities, high-level keywords → relationship tags, plus one-hop neighbors, merged (`hybrid` mode in this benchmark) | One process for both specific and general questions | In theory, broad questions get tagged facts, not a written summary (its paper reports beating GraphRAG on broad questions anyway) |
| **Fast-GraphRAG** | Personalized PageRank over entities, then relationship and chunk scores worked out from the entity scores | Multi-hop questions beyond 1 hop, at low cost | Chunks are scored after PageRank, not inside it |
| **HippoRAG2** | Question → triples, filtered by an LLM, then Personalized PageRank over entities **and** passage nodes together; returns top passages | Multi-hop questions, with strong grounding to real source text (good for faithfulness) | Not built for broad-theme summarization (no community-report equivalent) |

---

## Sources

**Frameworks**

- **GraphRAG** — Edge, D. et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* [arXiv:2404.16130](https://arxiv.org/abs/2404.16130). Code: [microsoft/graphrag](https://github.com/microsoft/graphrag). Docs: [microsoft.github.io/graphrag](https://microsoft.github.io/graphrag/)
- **LightRAG** — Guo, Z. et al. (2024). *LightRAG: Simple and Fast Retrieval-Augmented Generation.* [arXiv:2410.05779](https://arxiv.org/abs/2410.05779). Code: [HKUDS/LightRAG](https://github.com/HKUDS/LightRAG)
- **Fast-GraphRAG** — no paper; code and README: [circlemind-ai/fast-graphrag](https://github.com/circlemind-ai/fast-graphrag)
- **HippoRAG2** — Gutiérrez, B. J. et al. (2025). *From RAG to Memory: Non-Parametric Continual Learning for Large Language Models.* [arXiv:2502.14802](https://arxiv.org/abs/2502.14802). Code: [OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG)
- **HippoRAG (original)** — Gutiérrez, B. J. et al. (2024). *HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models.* [arXiv:2405.14831](https://arxiv.org/abs/2405.14831)

**Benchmark**

- **GraphRAG-Bench** — Xiang, Z. et al. (2025). *When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation.* [arXiv:2506.05690](https://arxiv.org/abs/2506.05690). Code: [GraphRAG-Bench/GraphRAG-Benchmark](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)
- **Metric definitions** — [`metrics_explained.md`](./metrics_explained.md) in this repository

---

*Next: [Generation stage](./03-generation-stage-explained.md) — how the retrieved context actually becomes a final answer, and how ROUGE-L, Coverage, Faithfulness, and Answer Correctness each check something different about that process.*
