# Metis Public Design Overview

This document explains the public design model of Metis without exposing internal implementation specifications.

## Product goal

Metis reduces the setup burden associated with AI development environments.

It does not try to generate finished AI applications. It gives developers a reliable environment that is ready for application work.

## Core model

### Recipe

A recipe describes a complete starting environment.

Examples:

- Agent
- RAG
- MCP server

### Capability

A capability is a reusable building block that can be composed into recipes or added later.

Examples:

- FastAPI
- Redis
- vector database
- embeddings
- LLM runtime

## Why composition matters

A generated environment should be able to evolve.

```text
metis init agent
metis add rag
```

If the Agent project already has FastAPI and an LLM provider, Metis should reuse them instead of creating duplicates.

## Project lifecycle

Conceptually:

```text
Inspect → Understand → Plan → Apply → Validate
```

For v0.1, the important behaviors are:

- inspect what is already present
- add only what is missing
- preserve compatible existing configuration
- validate the resulting environment
- update metadata after success

## Project metadata

Generated projects include:

```text
.metis/project.yaml
```

Metadata helps Metis understand the originating recipe, selections, and recorded capabilities.

Metadata is not the sole source of truth. Metis also inspects project evidence such as Docker Compose, environment templates, Python dependencies, and generated capability files.

## Safety model

Metis favors safe extension over regeneration.

- do not silently overwrite user-managed code
- do not duplicate services or dependencies
- fail clearly on incompatible capability conflicts
- keep repeatable operations idempotent
- validate before claiming success

## Developer ownership

Metis intentionally does not own:

- business logic
- prompt strategy
- chunking strategy
- retrieval strategy
- domain-specific agent behavior
- production architecture

## Current scope

```text
metis init rag
metis init agent
metis init mcp-server
metis add rag
metis inspect
metis doctor
```
