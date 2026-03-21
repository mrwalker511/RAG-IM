from ragcore.retrieval.vector_search import ChunkResult

_MAX_CONTEXT_CHARS = 12_000  # ~3k tokens — conservative budget

_TEMPLATE = """\
You are a helpful assistant. Answer the question below using only the provided context.
For each claim, cite the source document and chunk index in brackets, e.g. [doc.pdf, chunk 3].
If the context does not contain enough information, say so.

Context:
{context}

Question: {question}

Answer:"""


def build_prompt(query: str, chunks: list[ChunkResult]) -> str:
    context_parts: list[str] = []
    total_chars = 0

    for chunk in chunks:
        entry = f"[{chunk.filename}, chunk {chunk.chunk_index}]\n{chunk.content}"
        if total_chars + len(entry) > _MAX_CONTEXT_CHARS:
            break
        context_parts.append(entry)
        total_chars += len(entry)

    context = "\n\n---\n\n".join(context_parts) if context_parts else "(no context)"
    return _TEMPLATE.format(context=context, question=query)
