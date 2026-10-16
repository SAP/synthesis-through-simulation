#!/usr/bin/env bash
# =============================================================================
# Reproduce all Generalist Populator (GP) experiments from the paper.
#
# Each section corresponds to one block in RUN_NAME.log.
# Run directories are created under .runs/ with timestamped names.
#
# Prerequisites:
#   1. Set environment variables (see .env.example or README § Environment Setup)
#   2. Activate the venv: source .venv/bin/activate
#   3. Set up all environments first (see README § Setting Up Environments)
#
# Usage:
#   # Run everything (slow — approx. 20–40 GPU-hours depending on model)
#   bash scripts/run_gp_all_experiments.sh
#
#   # Run only one section (comment out the rest or use the environment variables):
#   SECTION=gp_infinite bash scripts/run_gp_all_experiments.sh
#
# SECTION options: gp_infinite | gp_k0 | gp_k3 | gp_k_ablation | gp_ablation_noheuristics | gp_ablation_noplan
# Leave unset (default) to run all sections.
#
# NOTE: Each run produces a NEW timestamped directory in .runs/. The paper
# results in the included .runs/ directories are pre-computed reference runs.
# =============================================================================

set -uo pipefail
cd "$(dirname "$0")/.."

SECTION="${SECTION:-all}"
N=100

log() { echo "[$(date '+%H:%M:%S')] $*" >&2; }

run_gp() {
    local env=$1
    local extra_flags=${2:-}
    log "Starting: env=$env flags=$extra_flags"
    # Reset DB and manifest to a clean baseline before each run
    synthesize --env "$env" setup
    synthesize --env "$env" snapshot
    synthesize --env "$env" explore reset 2>/dev/null || true
    synthesize --env "$env" batch \
        --synthesizer generalist_populator \
        --explore-mode staged \
        --n "$N" \
        $extra_flags
    log "Done: env=$env"
}

# =============================================================================
# Section 1: GP K=infinite (explore every run via interleaved mode)
# Paper: Table 2 main results, all 10 environments
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_infinite" ]]; then
    log "=== Section 1: GP K=infinite (explore_runs=100, same as K=3 but K=N) ==="
    for env in airline retail hr it_management banking ecommerce pharmacy forum university cloud; do
        run_gp "$env" "--explore-runs 100"
    done
    log "=== Section 1 complete ==="
fi

# =============================================================================
# Section 2: GP K=0 (no exploration — execute-only)
# Paper: K ablation (Table 3 / Figure k-ablation)
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_k0" ]]; then
    log "=== Section 2: GP K=0 (no exploration) ==="
    for env in airline retail banking ecommerce pharmacy forum university it_management hr cloud; do
        run_gp "$env" "--explore-runs 0"
    done
    log "=== Section 2 complete ==="
fi

# =============================================================================
# Section 3: GP K=3 (explore 3 cycles before switching to execute-only)
# Paper: K ablation (Table 3 / Figure k-ablation), includes obfuscated_airline
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_k3" ]]; then
    log "=== Section 3: GP K=3 ==="
    for env in airline retail banking ecommerce pharmacy forum university it_management hr cloud obfuscated_airline; do
        run_gp "$env" "--explore-runs 3"
    done
    log "=== Section 3 complete ==="
fi

# =============================================================================
# Section 4: K-value ablation on airline (K=1,5,10,20)
# Paper: Figure k-ablation (airline environment only)
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_k_ablation" ]]; then
    log "=== Section 4: K-value ablation (airline, K=1/5/10/20) ==="
    for k in 20 10 5 1; do
        log "--- K=$k ---"
        run_gp "airline" "--explore-runs $k"
    done
    log "=== Section 4 complete ==="
fi

# =============================================================================
# Section 5: Ablation — No Heuristics (K=3, --no-heuristics)
# Paper: Phase contribution analysis (Figure phase-contribution)
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_ablation_noheuristics" ]]; then
    log "=== Section 5: GP K=3 No-Heuristics ablation ==="
    for env in airline hr banking; do
        run_gp "$env" "--explore-runs 3 --no-heuristics"
    done
    log "=== Section 5 complete ==="
fi

# =============================================================================
# Section 6: Ablation — No Plan (K=3, --no-plan)
# Paper: Phase contribution analysis (Figure phase-contribution)
# =============================================================================
if [[ "$SECTION" == "all" || "$SECTION" == "gp_ablation_noplan" ]]; then
    log "=== Section 6: GP K=3 No-Plan ablation ==="
    for env in airline hr; do
        run_gp "$env" "--explore-runs 3 --no-plan"
    done
    log "=== Section 6 complete ==="
fi

log "=== All requested sections complete ==="
log "Run directories are in .runs/ — use scripts/compute_fidelity.py to compute metrics."
