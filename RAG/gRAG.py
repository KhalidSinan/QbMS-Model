from __future__ import annotations
from langchain_openai import ChatOpenAI

import os
from dataclasses import dataclass
from typing import Iterable, List

from dotenv import load_dotenv

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document

from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain.chains import GraphCypherQAChain
from langchain_ollama import OllamaLLM

load_dotenv()

# LLM config (swap provider if preferred)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Neo4j config
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://de12d823.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv(
    "NEO4J_PASSWORD", "kDkHpBHRYWOTKNoh7KAnIollhFE7lnugmLvmgGXzxVo")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")  # optional

# Transcript splitting
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Optional controlled schema (keeps the graph tidy)
ALLOWED_NODES = [
    "Person",         # Participant in the meeting
    "Email",          # Email address of a person
    "Username",       # Virtual username / handle
    "Organization",   # Company or department
    "Team",           # Team name
    "Meeting",        # Meeting itself
    "Topic",          # Discussion topics
    "Concept",
    "Framework",
    "Project",        # Project being discussed
    "Decision",       # Decisions made
    "ActionItem",     # Tasks assigned
    "Deliverable",    # Outputs or deliverables
    "DateTime",       # Meeting or deadlines
    "Tool",           # Software or tools mentioned
    "Role",           # Role of the person
    "Location",       # Can be virtual platform (Zoom/Teams) or physical
    "Document",       # Shared references/files
    "Message",        # Chat messages / contributions
    "TimeZone",       # For online participants
]

ALLOWED_RELATIONS = [
    # Attendance & participation
    "ATTENDS",         # (Person -> Meeting)
    "ORGANIZES",       # (Person -> Meeting)
    "HAS_ROLE",        # (Person -> Role)
    "BELONGS_TO",      # (Person -> Team/Organization)
    "JOINED_FROM",     # (Person -> Location/TimeZone)

    # Personal info
    "HAS_EMAIL",       # (Person -> Email)
    "HAS_USERNAME",    # (Person -> Username)

    # Meeting content
    "SPOKE_ABOUT",     # (Person -> Topic)
    "MENTIONS",        # (Person -> Project/Tool/Topic/Deliverable)
    "CREATED_DOCUMENT",  # (Person -> Document)
    "COMMENTED_ON",    # (Person -> Message/Document)

    # Decisions & actions
    "DECIDED",         # (Decision -> Topic/Project)
    "ASSIGNED_TO",     # (ActionItem -> Person)
    "DUE_ON",          # (ActionItem -> DateTime)
    "FOLLOW_UP_ON",    # (ActionItem -> Meeting/ActionItem)
    "PART_OF",         # (Topic/ActionItem/Decision -> Meeting/Project)

    # Relationships between messages/content
    "RESPONDS_TO",     # (Message -> Message)
    "RELATED_TO",      # (Message/Topic/Decision -> Topic/Project/Deliverable)
]


def make_llm():
    return ChatOpenAI(model_name=LLM_MODEL, temperature=TEMPERATURE, api_key=OPENAI_API_KEY)


def split_transcript(text: str) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "]
    )
    docs = [Document(page_content=chunk)
            for chunk in splitter.split_text(text)]
    return docs


def connect_graph() -> Neo4jGraph:
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )
    return graph


def ensure_constraints(graph: Neo4jGraph) -> None:
    """Create some helpful constraints (idempotent). Adjust as needed."""
    statements = [
        "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (n:Person) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT org_name IF NOT EXISTS FOR (n:Organization) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT team_name IF NOT EXISTS FOR (n:Team) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (n:Topic) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT project_name IF NOT EXISTS FOR (n:Project) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (n:ActionItem) REQUIRE n.id IS UNIQUE",
    ]
    for cypher in statements:
        try:
            graph.query(cypher)
        except Exception as e:
            print(f"Constraint skipped/failed: {cypher} -> {e}")


@dataclass
class GraphExtractionResult:
    graph_docs: list
    inserted: int


def extract_graph_from_docs(docs: List[Document]) -> GraphExtractionResult:
    """Use LLM to extract a knowledge graph as GraphDocument objects."""
    llm = make_llm()
    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=ALLOWED_NODES,
        allowed_relationships=ALLOWED_RELATIONS,
        strict_mode=False,
    )
    graph_docs = transformer.convert_to_graph_documents(docs)
    print('Graph Docs Done Successfully')
    print(graph_docs)
    return GraphExtractionResult(graph_docs=graph_docs, inserted=0)


def upsert_graph(graph: Neo4jGraph, graph_docs: list) -> int:
    """Insert graph documents into Neo4j. Returns number of relationships created."""
    # include_types=True preserves the node/edge types suggested by the LLM
    result = graph.add_graph_documents(
        graph_documents=graph_docs,
        include_source=True,   # keep source text reference on nodes/edges
    )
    # result is implementation-defined across versions; return a safe count if available
    try:
        rels = result.get("relationships", 0) if isinstance(
            result, dict) else 0
    except Exception:
        rels = 0
    return rels


def main():
    # 1) Connect to Neo4j and prep constraints
    graph = connect_graph()
    ensure_constraints(graph)

    # 2) Read the transcript
    transcript_file = "example_transcript.txt"
    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    # 3) Convert transcript -> documents -> graph documents
    docs = split_transcript(transcript_text)
    extraction = extract_graph_from_docs(docs)

    # 4) Upsert into Neo4j
    rel_count = upsert_graph(graph, extraction.graph_docs)
    print(
        f"Inserted/updated graph. Relationships created (approx): {rel_count}")


if __name__ == "__main__":
    main()
