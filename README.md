# Metis

**Build AI environments. Not setup scripts.**

Metis is an open-source CLI for scaffolding and evolving local AI development environments for **RAG**, **Agents**, and **MCP**.

It helps developers get from idea to a working environment quickly by generating the infrastructure, configuration, starter wiring, metadata, and diagnostics needed to start building.

> **Recipes create environments. Capabilities extend them. Inspect explains them. Doctor validates them.**

## Why Metis

AI projects often begin with the same setup work:

- Docker and Docker Compose
- Python project structure
- dependency wiring
- environment variables
- vector database setup
- optional Redis state
- health checks
- starter API/server wiring

Metis handles that setup so developers can focus on:

- application logic
- prompts
- retrieval strategy
- chunking
- tools
- workflows
- domain-specific agent behavior

## What Metis supports

### RAG

```bash
metis init rag
```

Create a local RAG development environment with choices such as:

- Vector DB: Qdrant or Chroma
- LLM: OpenAI or Anthropic
- Embeddings: OpenAI or Hugging Face
- Framework: FastAPI

Metis scaffolds the environment and starter wiring. Your application still owns retrieval strategy, chunking, prompts, and domain logic.

### Agents

```bash
metis init agent
```

Create an Agent development environment with choices such as:

- LLM: OpenAI or Anthropic
- Runtime: plain SDK or LangGraph
- State: none or Redis
- Framework: FastAPI

Metis gives you the plumbing so you can focus on tools, orchestration, and agent behavior.

### MCP Server

```bash
metis init mcp-server
```

Create a minimal Python MCP server with:

- stdio or streamable HTTP transport
- a safe example tool
- Docker support where applicable

## Core commands

### Create an environment

```bash
metis init agent
metis init rag
metis init mcp-server
```

### Preview before generating

```bash
metis init rag --name demo --dry-run
```

Dry-run resolves the recipe and your selections exactly like a normal `init`, then shows the generation plan before Metis writes anything.

The plan includes:

- recipe and project name
- target destination
- resolved selections
- capabilities
- files Metis would create

Dry-run is read-only. It does **not** create the project directory, write generated files, or create `.metis/project.yaml`.

Example:

```text
Metis generation plan

Recipe: rag
Project: demo
Destination: ./demo

Selections:
  vector_db: qdrant
  llm: openai
  embedding: openai
  framework: fastapi

Capabilities:
  python
  fastapi
  llm
  embeddings
  vector-db

Files:
  CREATE .env.example
  CREATE Dockerfile
  CREATE README.md
  CREATE app/main.py
  CREATE docker-compose.yml
  CREATE .metis/project.yaml

Dry run only. No files were written.
```

### Extend an existing project

```bash
metis add rag
```

Metis inspects what already exists, reuses compatible components, adds only what is missing, validates the result, and updates project metadata.

### Understand a project

```bash
metis inspect
```

Shows the originating recipe, selections, capabilities, and detected infrastructure.

### Validate local readiness

```bash
metis doctor
```

Checks the local development environment without modifying it.

Depending on the project, Doctor can validate:

- Docker availability
- Docker Compose availability
- Compose configuration
- application health
- Qdrant reachability
- Chroma reachability
- Redis reachability
- required provider environment variables

## A better way to build

Metis is designed to evolve with the project.

```text
Before init
metis init rag --dry-run

Day 1
metis init agent

Day 5
metis add rag

Anytime
metis inspect

Before development
metis doctor
```

The goal is simple:

> **Do not rebuild what already exists. Build on top of it.**

## Developer experience

### Minutes, not hours

Start with a working local environment instead of wiring infrastructure manually.

### Preview before apply

See what Metis plans to generate before it writes anything.

### Composable by design

Recipes create complete environments. Capabilities are reusable building blocks.

### Safe evolution

Metis preserves compatible existing configuration and avoids unnecessary regeneration.

### Understandable by default

Project metadata, `inspect`, and `doctor` make generated environments easier to reason about and troubleshoot.

## Install for local development

Metis is currently easiest to run directly from the repository.

```bash
git clone https://github.com/rajeshsgr/metis.git
cd metis

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .
```

Run the test suite:

```bash
python -m pytest
```

## Quick start

Preview a RAG project before creating anything:

```bash
metis init rag --name my-rag-project --dry-run
```

Review the plan, then run the same command without `--dry-run` when you are ready to generate the project.

Create an Agent project:

```bash
metis init agent
```

Or generate it into a specific output directory:

```bash
metis init agent --output /tmp/metis
```

Then:

```bash
cd /tmp/metis/my-agent
cp .env.example .env
docker compose up --build
```

Understand and validate the project:

```bash
metis inspect
metis doctor
```

## Example: RAG

Preview first:

```bash
metis init rag --name my-rag-project --output /tmp/metis --dry-run
```

Then generate:

```bash
metis init rag --output /tmp/metis
```

Choose the options you want, then:

```bash
cd /tmp/metis/my-rag-project
cp .env.example .env
docker compose up --build
```

Validate:

```bash
curl http://localhost:8000/health
metis inspect
metis doctor
```

## Example: evolve an Agent into Agent + RAG

Start with:

```bash
metis init agent
```

Later:

```bash
cd my-agent
metis add rag
```

Metis should reuse what already exists and add only the missing RAG capabilities.

Then:

```bash
metis inspect
metis doctor
```

## Project metadata

Every Metis-generated project contains:

```text
.metis/project.yaml
```

This records information such as:

- originating recipe
- project selections
- recorded capabilities

Metis does not blindly trust metadata. Commands that inspect or modify a project also compare it with the actual project files and configuration.

## Design principles

Metis is built around a few simple principles:

- **Preview before apply**
- **Composable by design**
- **Safe evolution**
- **Deterministic scaffolding**
- **Idempotent operations where applicable**
- **Developer-owned business logic**
- **Local-first developer experience**
- **Minimal changes over regeneration**

## Metis v0.1 scope

The first release intentionally keeps the product surface small:

```text
metis init rag
metis init agent
metis init mcp-server
metis init <recipe> --dry-run
metis add rag
metis inspect
metis doctor
```

The current release focuses on **local development scaffolding, planning, composition, and diagnostics**.

Production deployment, enterprise authentication, cloud provisioning, and observability are outside the current v0.1 scope.

## Website and documentation

The GitHub Pages website and lightweight usage documentation live under:

```text
docs/
```

Useful public docs:

- `docs/DESIGN.md`
- `docs/ROADMAP.md`

## Contributing

Contributions are welcome.

Please read:

```text
CONTRIBUTING.md
```

before proposing larger changes.

## Project status

Metis is an early open-source project and the APIs and generated structures may evolve.

Feedback, bug reports, and feature proposals are welcome.

---

**Stop configuring. Start building.**
