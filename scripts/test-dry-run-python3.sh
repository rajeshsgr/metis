#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="dry-run-test"

echo "==> Cleaning previous test artifacts"
rm -rf "$PROJECT_NAME"

echo "==> Running dry-run"
printf '\n\n\n\n' | python3 -m metis init rag --name "$PROJECT_NAME" --dry-run

echo "==> Verifying dry-run created nothing"
if [ -d "$PROJECT_NAME" ]; then
  echo "FAIL: $PROJECT_NAME directory was created during dry-run"
  exit 1
fi

echo "PASS: dry-run made no filesystem changes"

echo
echo "==> Running normal init"
printf '\n\n\n\n' | python3 -m metis init rag --name "$PROJECT_NAME"

echo "==> Verifying project was created"
if [ ! -d "$PROJECT_NAME" ]; then
  echo "FAIL: normal init did not create $PROJECT_NAME"
  exit 1
fi

if [ ! -f "$PROJECT_NAME/.metis/project.yaml" ]; then
  echo "FAIL: .metis/project.yaml was not created"
  exit 1
fi

echo "PASS: normal init works"

echo
echo "==> Cleaning up"
rm -rf "$PROJECT_NAME"

echo
echo "All dry-run smoke tests passed."
