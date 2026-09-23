# Retrieval Stage — Explained

## What is retrieval?

Indexing (see [01-indexing-stage-explained.md](./01-indexing-stage-explained.md)) is **offline** — it happens once, before any question exists, and builds one general-purpose graph containing everything in the document. Retrieval is the opposite: it's **online** — it runs fresh, every single time a question comes in.

Indexing has no way to know in advance which slice of the graph any future question will need — "relevant" is entirely defined by the specific question being asked. Retrieval's job is to take one specific question, search the graph indexing already built, and pull out the small piece that's actually relevant right now.

That pulled-out material is called the **retrieved context**. It's the input handed to the LLM in the next stage (generation) to write an answer.

## The shared starting point: seeds, then expand

Every framework turns the question into something comparable against the graph — usually via **embeddings** (question meaning vs. node meaning) or **keywords** (specific words matched against entity names/tags). This produces a small set of **seed nodes**: starting points in the graph.

Retrieval never compares the question directly against *every* node. Why: direct similarity only finds nodes that *look like* the question in wording. But some relevant nodes (like "Sara" in a question that never mentions her by name) are only relevant because they're **connected**, through a chain of edges, to something that does match directly. This is the same reason a graph was built in the first place (see indexing doc) — multi-hop reasoning has to actually get *executed* somewhere, and that's here: seeds are found by direct matching, then the graph's edges carry relevance to everything connected to those seeds.

---

## GraphRAG: Local Search vs. Global Search

GraphRAG has two separate retrieval modes, chosen based on question type:

- **Local Search** (specific questions): find seed entities via embedding similarity to the question, then pull in their **direct (1-hop)** relationships, claims, and source text chunks.
- **Global Search** (broad, thematic questions): skips entities entirely. Searches across **community reports** (built during indexing) using a map-reduce process — check the question's relevance against each report, then combine the useful ones.

**Why the wrong mode fails:** Local Search on a broad question fails because a broad question doesn't resemble any single entity's description, and even if it picked seeds, it only expands to a narrow 1-hop neighborhood — never the big picture. Global Search on a specific question fails because community reports are compressed summaries; a precise detail may get flattened out of the summary entirely, and checking every report for one fact is expensive overkill.

## LightRAG: dual-level keyword retrieval

The question is split by an LLM into:
- **Low-level keywords** (specific things) → matched against the entity vector index.
- **High-level keywords** (general topics) → matched against the relationship-keyword vector index.

Both run on every question (no separate "modes" like GraphRAG), and results are merged.

**Gap vs. GraphRAG's Global Search:** the "high-level" side still only matches individual relationship-keyword tags — scattered facts that happen to share a keyword. It never produces a genuine synthesized summary the way a community report does. It approximates broad-question coverage; it doesn't replicate real summarization.

## Fast-GraphRAG and HippoRAG2: Personalized PageRank (PPR)

Both use the same core trick, borrowed from PageRank (the original Google ranking algorithm): instead of ranking by "how many pages link here," **Personalized** PageRank injects a relevance "boost" at the seed nodes matched to the question, and lets that score **spread outward** through the graph's edges, fading with each hop.

**Why this beats Local Search on hard questions:** Local Search has a hard cutoff at 1 hop — anything further away is structurally unreachable, no matter how relevant. PPR has no hard cutoff; relevance keeps spreading across as many hops as the graph allows, just weaker with distance. So multi-hop questions (2, 3+ hops from a seed) can still surface, just ranked lower than closer facts.

**The difference between the two:**
- **Fast-GraphRAG**: its graph only has entity/relationship nodes (indexing added nothing extra). PPR ranks entities, then a **separate step afterward** traces top entities back to source chunks to build the actual context text. Risk: an entity may appear in several chunks, so a heuristic has to pick which one(s) to include — an approximation layered on *after* the real relevance computation, which can pick a chunk that mentions the entity but isn't the one with the specific needed fact.
- **HippoRAG2**: passage nodes are already part of the graph (from indexing). PPR spreads relevance across entity nodes **and** passage nodes in the *same* pass — so a passage's score already reflects genuine graph-connectivity to the question, no separate "go find the source chunk" step, and no extra approximation layer.

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
| **LightRAG** | Dual-level: low-level keywords → entities, high-level keywords → relationship tags, merged | Runs one unified process for both specific and general questions | Broad questions get scattered tagged facts, not real synthesis |
| **Fast-GraphRAG** | Personalized PageRank over entities, then a separate step to trace back to source chunks | Multi-hop questions beyond 1 hop, at low cost | Extra approximation step when picking which source chunk to use for a top-ranked entity |
| **HippoRAG2** | Personalized PageRank over entities **and** passage nodes together | Multi-hop questions, with strong grounding to real source text (good for faithfulness) | Not built for broad-theme summarization (no community-report equivalent) |

---

*Next: [Generation stage](./03-generation-stage-explained.md) — how the retrieved context actually becomes a final answer, and how ROUGE-L, Coverage, Faithfulness, and Answer Correctness each check something different about that process.*
