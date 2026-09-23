# Indexing Stage — Explained

## What is indexing?

Indexing is the **offline** stage. It happens once, before anyone asks a question. The framework reads the raw text and builds a **knowledge graph** out of it: entities ("things," like people, companies, places) and relationships ("how those things connect").

## Why build a graph instead of just storing text chunks?

Plain/vanilla RAG also indexes once — it just splits text into chunks and stores them (usually as embeddings). The problem: each chunk is self-contained, and retrieval works by matching the *question's meaning* against a chunk's meaning. If the facts needed to answer a question are spread across several chunks that never sit next to each other, no single chunk looks similar enough to the question to be retrieved — even though every individual fact is written down somewhere.

**Example:** "Ahmad works at Company X." / "Sara manages Company X." / "Company X is based in Prague and makes medical devices." — three separate sentences, maybe far apart in the document.

A question like *"who works under the person who runs the Prague medical-device company?"* needs all three facts connected. No single chunk contains that chain, so chunk-similarity search struggles.

A graph fixes this because each fact becomes its own **edge**, stored permanently. Retrieval can then **hop** from node to node (Company X → its manager → that manager's team) and stitch the chain together. This is called **multi-hop reasoning**, and it's the main thing graphs add that chunk-search structurally cannot do.

## The shared core mechanism (every framework does this)

1. Split the document into chunks (same as vanilla RAG).
2. For each chunk, prompt an LLM: *"List every entity mentioned, and every relationship between entities."*
3. The LLM returns a structured list per chunk.
4. Merge matching entities/relationships across chunks into one graph.

**A known weak spot:** most frameworks merge only on **exact matching name strings**. If the same entity is called "Company X" in one chunk and "the company" in another, they usually do **not** get merged — the graph ends up more fragmented than it should be (extra isolated pieces, disconnected components), not because the facts are unrelated, but because the names didn't match.

On top of this shared core, each framework adds something different.

---

## GraphRAG (Microsoft)

Adds two extra layers on top of the shared core:

- **Claims** *(optional, off by default in current versions)* — an assertion about one entity, with a truth status (`TRUE` / `FALSE` / `SUSPECTED`) and a date. Different from a relationship: a relationship says "a link exists"; a claim says "someone alleged something, and here's how confident we are."
- **Communities** — after the graph is built, the **Leiden algorithm** (no LLM, purely structural — it just looks at edge patterns) groups entities that are more tightly connected to each other than to the rest of the graph. Done at multiple zoom levels (like continent → country → city). Then an LLM writes a short **community report** summarizing each group.

**Why communities matter:** multi-hop traversal is great for specific, connected questions ("who works under X"), but useless for broad, thematic questions ("what are the main topics in this dataset?"). No single hop-chain answers that — you need something pre-summarized. That's what community reports are for.

**DIGIMON classification:** entities + relationships + text descriptions, no relationship keywords → **Textual KG**.

## LightRAG

Skips communities entirely. Instead, in the *same* LLM call that extracts entities and relationships, it also attaches keywords:

- Every **entity** gets one key: its own name.
- Every **relationship** gets one or more **topic keywords** (e.g., "employment," "medical industry").

Later, a question gets split into **low-level keywords** (specific things → matched against entity names) and **high-level keywords** (general topics → matched against relationship keywords). This is **dual-level retrieval**.

**Advantage vs. GraphRAG:** cheaper (no separate whole-graph clustering pass, no per-community report-writing), and easier to update incrementally — adding one new document doesn't require recomputing anything about the rest of the graph's structure. GraphRAG may need to redo clustering as the graph grows.

**Disadvantage vs. GraphRAG:** because keywords are assigned per relationship independently, with nothing looking at the graph as a whole, two relationships about the same real topic might get worded differently ("employment" vs. "job") and never get linked. Even when keywords do match, the result is just a pile of tagged relationships — not a written summary. Broad "what's this dataset about" questions get a weaker answer than GraphRAG's community report.

**DIGIMON classification:** entities + relationships + text descriptions + relationship keywords → **Rich KG** (the richest of the frameworks covered here).

## Fast-GraphRAG

Indexing is just the shared core — nothing extra. No claims, no communities, no keyword tags.

**Trade-off:** this makes it the cheapest and fastest to index (its own claims cite ~6x cost savings vs. GraphRAG), but it loses GraphRAG's strength on broad, thematic questions, since there's no community-report equivalent. It tries to make up for this at **retrieval time** instead, using a technique borrowed from HippoRAG (Personalized PageRank) — covered in the retrieval-stage document.

## HippoRAG2

Adds something structurally different from the other three:

1. Extracts entities and relationships like everyone else (using OpenIE-style extraction).
2. Also puts the **text passages/chunks themselves into the graph as nodes** — not just entities. A passage node connects to the entity nodes it mentions.
3. Every node — entity **and** passage — gets an **embedding**.

**Why passage nodes matter:** when the LLM extracts a relationship, it compresses the original sentence into something short (`Ahmad —works at→ Company X`), throwing away the original wording and detail. A pure entity/relationship graph can tell you *that* a fact exists, but can't hand back the *actual sentence* that proved it. Passage nodes fix this — after graph traversal finds the relevant entities, the connected passage nodes can be pulled directly, giving back real, groundable text. This matters for the generation stage, where the **Faithfulness** metric checks whether the generated answer's claims are actually supported by the retrieved context — real text supports that check better than a compressed fact does.

**Why embeddings matter:** they give a second way to catch entity matches that exact-name-matching would miss (a partial fix for the fragmentation weak spot mentioned above).

**DIGIMON classification:** doesn't fit the richness ladder cleanly — its innovation (passage nodes) isn't something the ladder measures. In terms of description richness alone, it's closer to a bare **Knowledge Graph** (row 3).

---

## Comparison table

| Framework | Extra indexing layer | Cost/speed | Good for | Weak for |
|---|---|---|---|---|
| **GraphRAG** | Claims (optional) + Communities/reports | Most expensive (extra clustering + report-writing pass) | Broad, thematic questions ("what are the main topics?") | Cost and incremental updates (may need to redo clustering as data grows) |
| **LightRAG** | Relationship keywords (same LLM call) | Cheaper than GraphRAG, easy incremental updates | Specific questions matching entity names or relationship topics (dual-level retrieval) | Broad questions — no real summary, just scattered tags |
| **Fast-GraphRAG** | None (bare graph only) | Cheapest/fastest to index | Specific, connected questions (via multi-hop traversal); relies on retrieval-time PageRank to compensate | Broad, thematic questions — no community-style summary at all |
| **HippoRAG2** | Passage nodes + embeddings on every node | Lightweight indexing, but adds passage nodes/embeddings | Questions needing real, groundable text (good for faithfulness); partially reduces name-mismatch fragmentation | Not built for broad-theme summarization either — its strength is grounding, not summarizing |

**Bottom line:** GraphRAG and LightRAG solve the "broad theme" problem differently (structural clustering + summary vs. lightweight keyword tags); GraphRAG's answer is richer but costlier. Fast-GraphRAG and HippoRAG2 both skip that problem at indexing time and lean on smarter retrieval instead — Fast-GraphRAG for raw speed, HippoRAG2 for text-grounded accuracy.

---

*Next: [Retrieval stage](./02-retrieval-stage-explained.md) — how each framework actually walks the graph it built here to produce "retrieved contexts."*
