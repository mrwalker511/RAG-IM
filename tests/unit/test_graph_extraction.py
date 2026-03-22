from types import SimpleNamespace

from ragcore.graph.extraction import extract_graph_from_chunks, normalize_entity_name


def test_normalize_entity_name_lowercases_and_strips_noise():
    assert normalize_entity_name("Acme, Inc.") == "acme inc"


def test_extract_graph_from_chunks_finds_entities_and_relations():
    chunks = [
        SimpleNamespace(
            chunk_index=0,
            content="Alice works with Bob at Acme Corp. Alice joined Acme Corp in 2024.",
        )
    ]

    extraction = extract_graph_from_chunks(chunks)

    entity_names = {entity.normalized_name for entity in extraction.entities}
    assert "alice" in entity_names
    assert "bob" in entity_names
    assert "acme corp" in entity_names
    assert extraction.relations
