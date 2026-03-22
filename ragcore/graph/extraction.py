from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))*\b")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_STOP_ENTITIES = {
    "A",
    "An",
    "And",
    "But",
    "For",
    "He",
    "Her",
    "His",
    "I",
    "If",
    "In",
    "It",
    "Its",
    "No",
    "Not",
    "Of",
    "On",
    "Or",
    "Our",
    "She",
    "That",
    "The",
    "Their",
    "There",
    "They",
    "This",
    "Those",
    "To",
    "We",
    "What",
    "When",
    "Where",
    "Who",
    "Why",
    "You",
}


@dataclass
class ExtractedEntity:
    name: str
    normalized_name: str
    entity_type: str
    description: str
    mention_count: int
    chunk_indices: list[int]


@dataclass
class ExtractedRelation:
    source_normalized_name: str
    target_normalized_name: str
    relation_type: str
    description: str
    mention_count: int
    chunk_indices: list[int]


@dataclass
class GraphExtraction:
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


def normalize_entity_name(value: str) -> str:
    parts = _WORD_RE.findall(value.lower())
    return " ".join(parts).strip()


def _entity_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for match in _ENTITY_RE.finditer(text):
        candidate = " ".join(match.group(0).split())
        if candidate in _STOP_ENTITIES:
            continue
        if len(candidate) < 2:
            continue
        candidates.append(candidate)
    return candidates


def _relation_type(sentence: str, source: str, target: str) -> str:
    lowered = sentence.lower()
    for verb in ("acquired", "built", "created", "developed", "founded", "joined", "led", "owns", "supports", "uses", "works"):
        if verb in lowered:
            return verb
    if " and " in lowered:
        return "associated_with"
    return "related_to"


def extract_graph_from_chunks(chunk_results: list) -> GraphExtraction:
    entity_map: dict[str, dict] = {}
    relation_map: dict[tuple[str, str, str], dict] = {}

    for chunk in chunk_results:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(chunk.content) if s.strip()]
        for sentence in sentences:
            names = []
            seen_names: set[str] = set()
            for name in _entity_candidates(sentence):
                normalized = normalize_entity_name(name)
                if not normalized or normalized in seen_names:
                    continue
                seen_names.add(normalized)
                names.append((name, normalized))

                current = entity_map.setdefault(
                    normalized,
                    {
                        "name": name,
                        "entity_type": "named_entity",
                        "description": sentence[:280],
                        "mention_count": 0,
                        "chunk_indices": set(),
                    },
                )
                current["mention_count"] += 1
                current["chunk_indices"].add(chunk.chunk_index)

            for idx in range(len(names)):
                for jdx in range(idx + 1, len(names)):
                    source_name, source_norm = names[idx]
                    target_name, target_norm = names[jdx]
                    if source_norm == target_norm:
                        continue
                    relation_type = _relation_type(sentence, source_name, target_name)
                    key = (source_norm, target_norm, relation_type)
                    current = relation_map.setdefault(
                        key,
                        {
                            "description": sentence[:280],
                            "mention_count": 0,
                            "chunk_indices": set(),
                        },
                    )
                    current["mention_count"] += 1
                    current["chunk_indices"].add(chunk.chunk_index)

    entities = [
        ExtractedEntity(
            name=data["name"],
            normalized_name=normalized,
            entity_type=data["entity_type"],
            description=data["description"],
            mention_count=data["mention_count"],
            chunk_indices=sorted(data["chunk_indices"]),
        )
        for normalized, data in entity_map.items()
    ]

    relations = [
        ExtractedRelation(
            source_normalized_name=source_norm,
            target_normalized_name=target_norm,
            relation_type=relation_type,
            description=data["description"],
            mention_count=data["mention_count"],
            chunk_indices=sorted(data["chunk_indices"]),
        )
        for (source_norm, target_norm, relation_type), data in relation_map.items()
    ]

    return GraphExtraction(entities=entities, relations=relations)
