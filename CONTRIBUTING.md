# Contributing to Metis

Thanks for your interest in contributing.

Metis aims to make AI development environments easier to create, understand, and evolve. Contributions should preserve that simplicity.

## Ways to contribute

- fix bugs
- improve generated project quality
- improve documentation
- add tests
- propose new recipes
- propose reusable capabilities
- improve developer experience
- report compatibility issues

## Before you start

For larger changes, open an issue first so the problem and direction can be discussed.

Small fixes and documentation improvements can usually go directly to a pull request.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
```

Run tests:

```bash
python -m pytest
```

## Contribution principles

### Preserve existing behavior
Avoid unrelated changes when implementing a focused feature or fix.

### Prefer composition over duplication
Reuse existing building blocks when possible.

### Keep generated projects simple
Metis should scaffold infrastructure and starter wiring, not impose unnecessary application architecture.

### Preserve user-owned code
Extensions should avoid overwriting user-managed application logic.

### Keep operations deterministic
The same inputs should produce predictable output.

### Keep operations idempotent where applicable
Running the same safe operation twice should not create duplicates.

### Add tests
New behavior should include automated coverage where practical.

## Pull request checklist

- [ ] Change is focused
- [ ] Existing behavior is preserved
- [ ] New behavior is tested
- [ ] `python -m pytest` passes
- [ ] Generated Compose is valid where applicable
- [ ] User-managed files are not unnecessarily overwritten
- [ ] Docs are updated if behavior changes

## Proposing a recipe

Describe:

- the developer problem
- intended workflow
- major building blocks
- what Metis should generate
- what the developer still owns
- how the recipe composes with existing capabilities

## Proposing a capability

Describe:

- what it provides
- what it requires
- how it is detected
- how it composes
- conflict behavior
- idempotency behavior

## Reporting bugs

Please include:

- Metis version or commit
- OS
- Python version
- Docker version if relevant
- command executed
- expected behavior
- actual behavior
- logs or error output

Do not include secrets or API keys.

## Code of conduct

Be respectful, constructive, and specific. Critique ideas and implementations, not people.
