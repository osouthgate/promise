#!/bin/bash
# Runs promise's behaviour evals with `claude plugin eval`, on the credential Claude Code
# is signed in with (a claude.ai subscription counts against the plan's usage).
#   bash evals/run.sh                 every case, 3 runs each
#   bash evals/run.sh --tag train     the cases a change may be tuned on
#   bash evals/run.sh --tag test      the held-out cases, only to accept a change
#   bash evals/run.sh --runs 1        one run each, while iterating
# Extra flags pass through to `claude plugin eval` (see evals/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
exec claude plugin eval . \
  --trust-plugin --scaffold \
  --allow-tools Bash Write Edit \
  --ablation none \
  -j 4 \
  --max-cost-usd "${EVAL_MAX_COST_USD:-20}" \
  "$@"
