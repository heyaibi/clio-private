#!/usr/bin/env bash
# Copyright 2026 Agent Memoir Developers (https://agentmemoir.com/)
# SPDX-License-Identifier: Apache-2.0
#
# Clio unattended phase driver.
#
# Canonical layout: this script lives at
# private/clio-private/harness/phase-driver.sh in the nested private repo.
# Every invocation below runs with the repo root as cwd. Call from the
# root, e.g.:
#   bash private/clio-private/harness/phase-driver.sh --check
#
#   phase-driver.sh [--dry-run]                  # cron entrypoint
#   phase-driver.sh --check                      # report environment readiness
#   phase-driver.sh --self-test                  # hermetic guard/halt/notify test
#   phase-driver.sh --stop                       # stop the live run (halt + Ctrl-C)
#   phase-driver.sh --session <N> <phase-file>   # one phase, run inside tmux
#
# The server reserves the selected phase in the private coordination branch
# before tmux starts. A coordination fetch/push failure is fail-closed.
#
# Cron runs the driver every few minutes. It does nothing while a phase is
# running or while the line is halted; otherwise it starts the lowest
# uncompleted phase in the tmux session named below. A phase that ends
# blocked/rejected/errored, OR that is stopped by a signal (Ctrl-C / tmux
# kill-session), writes a halt marker and stops the line until the operator
# clears it. Start/end/halt notifications go to Discord through the Hermes
# profile below.
#
# Optional untracked overrides live in
# private/clio-private/runs/.driver.env (sourced if present):
# HERMES_PROFILE_NAME, DISCORD_CHANNEL, DISCORD_FALLBACK_CHANNEL,
# HEARTBEAT_URL, STALE_AFTER_SEC, LOG_KEEP_DAYS, TMUX_WIDTH, TMUX_HEIGHT,
# PHASE_MACHINE_ID, PHASE_COORDINATION_BRANCH.
#
# Local test hooks (never set these in cron):
#   DISABLE_NOTIFY=1      log notifications instead of sending them
#   DISABLE_DISCORD=1     alias for disabling Discord sends (same effect today)
#   DRIVER_STUB_RC=<n>    skip runner.py; pretend it exited with rc <n>
#   DRIVER_STUB_SLEEP=<s> how long the stub "works" (default 2)
#   DRIVER_RUN_DIR=<dir>  isolate runtime state (used by --self-test)
set -euo pipefail

# Resolve the repo root from this script's location. Falls back to git
# when the layout is unexpected.
_SCRIPT_SRC="${BASH_SOURCE[0]}"
while [ -L "$_SCRIPT_SRC" ]; do
  _SCRIPT_SRC="$(readlink "$_SCRIPT_SRC")"
  case "$_SCRIPT_SRC" in
    /*) : ;;
    *) _SCRIPT_SRC="$(dirname "${BASH_SOURCE[0]}")/$_SCRIPT_SRC" ;;
  esac
done
_SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT_SRC")" && pwd)"
if [ "$(basename "$_SCRIPT_DIR")" = "harness" ] \
  && [ "$(basename "$(dirname "$_SCRIPT_DIR")")" = "clio-private" ]; then
  REPO="$(cd "$_SCRIPT_DIR/../../.." && pwd)"
else
  REPO="$(cd "$_SCRIPT_DIR/.." && pwd)"
fi
unset _SCRIPT_SRC _SCRIPT_DIR
if [ ! -f "$REPO/Cargo.toml" ] && command -v git >/dev/null 2>&1; then
  _GIT_ROOT="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "${_GIT_ROOT:-}" ] && REPO="$_GIT_ROOT"
  unset _GIT_ROOT
fi

# Canonical private locations (all invoked with $REPO as cwd).
PRIV="private/clio-private"
WF="$REPO/$PRIV/runs"
HARNESS="$REPO/$PRIV/harness"
NOTIFIER="$HARNESS/phase_notifications.py"

# Optional untracked overrides; keep secrets/ids out of the committed file.
# shellcheck disable=SC1091
[ -f "$WF/.driver.env" ] && . "$WF/.driver.env"

: "${HERMES_PROFILE_NAME:=not-james-gosling}"
: "${DISCORD_CHANNEL:=1546601332276727828}"
: "${DISCORD_FALLBACK_CHANNEL:=}"
: "${HEARTBEAT_URL:=}"
: "${STALE_AFTER_SEC:=2700}"
: "${LOG_KEEP_DAYS:=7}"
: "${DRIVER_RUN_DIR:=$WF/.driver}"
: "${SESSION_NAME:=development}"
: "${TMUX_WIDTH:=164}"
: "${TMUX_HEIGHT:=48}"
: "${PHASE_MACHINE_ID:=${CLIO_MACHINE_ID:-server-01}}"
: "${PHASE_COORDINATION_BRANCH:=${CLIO_PHASE_COORDINATION_BRANCH:-master}}"
export CLIO_MACHINE_ID="$PHASE_MACHINE_ID"
export CLIO_PHASE_COORDINATION_BRANCH="$PHASE_COORDINATION_BRANCH"

PIPELINE="private/clio-private/harness/pipelines/default.yaml"
SESSION="$SESSION_NAME"
PROFILE="$HERMES_PROFILE_NAME"
CHANNEL="$DISCORD_CHANNEL"
FALLBACK="$DISCORD_FALLBACK_CHANNEL"
RUN_DIR="$DRIVER_RUN_DIR"
LOCK="$RUN_DIR/driver.lock"
HALT="$RUN_DIR/halted"
STALL="$RUN_DIR/stalled"
CURRENT="$RUN_DIR/current"
PIDFILE="$RUN_DIR/pid"
NOTIFY_BROKEN="$RUN_DIR/notify-broken"
LOG="$RUN_DIR/driver.log"
DRY_RUN=0
CUR_PHASE=""
CUR_PHASE_FILE=""
_STOPPED=0
NOTIFY_DEAD=0

# cron gives a minimal PATH; add common locations as FALLBACKS (append, never
# shadow). A pyenv/conda python3 earlier in PATH must keep winning, because a
# homebrew python3 may lack PyYAML and crash runner.py on import.
export PATH="${PATH:-/usr/bin:/bin}:/usr/bin:/bin:$HOME/.local/bin:$HOME/homebrew/bin:/opt/homebrew/bin:/usr/local/bin"

# Pick a python3 that can actually run runner.py (needs PyYAML), by absolute
# path so the choice survives into the tmux session regardless of its PATH.
PYTHON=""
resolve_python() {
  local cand
  for cand in "${PYTHON:-}" "$(command -v python3 2>/dev/null)" \
              "$HOME/.pyenv/shims/python3" /opt/homebrew/bin/python3 \
              /usr/local/bin/python3 /usr/bin/python3; do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    if "$cand" -c 'import yaml' >/dev/null 2>&1; then PYTHON="$cand"; return 0; fi
  done
  return 1
}

ts() { date +%Y-%m-%dT%H:%M:%S%z; }

log() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s %s\n' "$(ts)" "$*"
  else
    printf '%s %s\n' "$(ts)" "$*" >>"$LOG"
  fi
}

# log, and also speak on stdout so a manual run is not silent (cron captures it).
say() { log "$*"; [ "$DRY_RUN" = 1 ] && return 0; printf '%s\n' "$*"; }

resolve_python || PYTHON="python3"

# Best-effort send: bounded by a timeout (when available) and with stdin
# closed, so a hung or interactive hermes can never stall the run.
send_one() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 20 hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout 20 hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  else
    hermes -p "$PROFILE" send --to "$1" "$2" </dev/null >>"$LOG" 2>&1
  fi
}

# Notifications are strictly best-effort: a missing profile, a dead Discord or a
# hung hermes must never block or halt the pipeline. On total failure the channel
# is marked dead for this process, so we stop retrying and stop spamming.
notify() {
  local msg="$1" target="discord:$CHANNEL"
  if [ "$NOTIFY_DEAD" = 1 ]; then
    log "notify skipped (channel unavailable): $msg"
    return 0
  fi
  if [ -n "${DISABLE_NOTIFY:-}" ] || [ -n "${DISABLE_DISCORD:-}" ]; then
    log "notify (disabled): $msg"
    return 0
  fi
  if ! command -v hermes >/dev/null 2>&1; then
    log "notify skipped (hermes not on PATH): $msg"
    return 0
  fi
  if send_one "$target" "$msg"; then
    log "notify ok: $msg"; rm -f "$NOTIFY_BROKEN"; return 0
  fi
  sleep 2
  if send_one "$target" "$msg"; then
    log "notify ok (retry): $msg"; rm -f "$NOTIFY_BROKEN"; return 0
  fi
  if [ -n "$FALLBACK" ] && send_one "discord:$FALLBACK" "$msg"; then
    log "notify via fallback channel: $msg"; return 0
  fi
  printf 'notify broken at %s: %s\n' "$(ts)" "$msg" >"$NOTIFY_BROKEN"
  NOTIFY_DEAD=1
  log "notify FAILED (wrote $NOTIFY_BROKEN); further sends skipped this run: $msg"
}

notify_phase() {
  local phase_file="$1" event="$2" reason="${3:-}" exit_code="${4:-}"
  local quiet_minutes="${5:-45}" message phase_number
  local args=(--phase-file "$phase_file" --event "$event" --quiet-minutes "$quiet_minutes")
  [ -n "$reason" ] && args+=(--reason "$reason")
  [ -n "$exit_code" ] && args+=(--exit-code "$exit_code")
  message="$("$PYTHON" "$NOTIFIER" "${args[@]}" 2>/dev/null || true)"
  if [ -n "$message" ]; then
    notify "$message"
    return 0
  fi
  phase_number="${phase_file##*/phase-}"
  phase_number="${phase_number%%-*}"
  notify "Phase ${phase_number:-unknown} needs attention."
}

phase_state() {
  local file="$WF/phase-$(printf '%06d' "$1")/run.json"
  "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("state",""))' \
    "$file" 2>/dev/null || true
}

# A signal-driven stop must halt and notify: bash dies before any trailing
# code after a signal, so the work is done in a trap, marker first. (Ctrl-C
# reaches this; tmux kill-session does NOT signal the pane, which is why the
# driver also records the session PID and treats a live PID with no session
# as an orphan.)
on_stop() {
  local rc="$1"
  [ "$_STOPPED" = 1 ] && exit "$rc"
  _STOPPED=1
  if [ -n "$CUR_PHASE" ]; then
    printf 'phase %s stopped by signal (rc=%s) at %s\n' \
      "$CUR_PHASE" "$rc" "$(ts)" >"$HALT"
    notify_phase "$CUR_PHASE_FILE" stopped-signal
  fi
  rm -f "$CURRENT" "$PIDFILE"
  exit "$rc"
}

run_session() {
  local number="$1" rel="$2" rc=0 state
  CUR_PHASE="$number"
  CUR_PHASE_FILE="$rel"
  mkdir -p "$RUN_DIR"
  trap 'on_stop 129' HUP
  trap 'on_stop 130' INT
  trap 'on_stop 143' TERM
  printf '%s\n' "$$" >"$PIDFILE"
  cd "$REPO"
  export CLIO_MACHINE_ID="${CLIO_MACHINE_ID:-$PHASE_MACHINE_ID}"
  notify_phase "$rel" started
  if [ -n "${DRIVER_STUB_RC:-}" ]; then
    log "STUB mode: simulating runner.py (rc=$DRIVER_STUB_RC)"
    sleep "${DRIVER_STUB_SLEEP:-2}"
    rc="$DRIVER_STUB_RC"
  else
    "$PYTHON" "$HARNESS/runner.py" --pipeline "$PIPELINE" \
      --input "phase_number=$number" --input "phase_file=$rel" || rc=$?
  fi
  state="$(phase_state "$number")"
  case "$rc" in
    0)   notify_phase "$rel" completed ;;
    3)   : ;;
    130) notify_phase "$rel" interrupted "the process received an interrupt signal" ;;
    *)   printf 'phase %s rc=%s state=%s at %s\n' \
           "$number" "$rc" "${state:-unknown}" "$(ts)" >"$HALT"
          notify_phase "$rel" stopped "" "$rc" ;;
  esac
  rm -f "$CURRENT" "$PIDFILE"
  exit "$rc"
}

tmux_busy() {
  tmux has-session -t "$SESSION" 2>/dev/null || return 1
  # A dead-but-retained pane (remain-on-exit) must not block the line forever.
  if [ "$(tmux list-panes -t "$SESSION" -F '#{pane_dead}' 2>/dev/null | sort -u)" = "1" ]; then
    log "stale dead session '$SESSION'; reclaiming it"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    return 1
  fi
  return 0
}

newest_mtime() {
  local newest=0 f m
  for f in "$@"; do
    [ -f "$f" ] || continue
    m="$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)"
    [ "$m" -gt "$newest" ] && newest="$m"
  done
  printf '%s\n' "$newest"
}

# While a session is live, alert once if its output has gone quiet too long.
check_stall() {
  [ -f "$STALL" ] && return 0
  local n phase_dir newest now age phase_file
  n="$(cat "$CURRENT" 2>/dev/null || true)"
  [ -n "$n" ] || return 0
  phase_dir="$WF/phase-$(printf '%06d' "$n")"
  newest="$(newest_mtime "$RUN_DIR/session-$n.log" "$phase_dir"/*)"
  [ "$newest" -gt 0 ] || return 0
  now="$(date +%s)"; age=$((now - newest))
  if [ "$age" -gt "$STALE_AFTER_SEC" ]; then
    printf 'stalled: phase %s no output for %ss at %s\n' \
      "$n" "$age" "$(ts)" >"$STALL"
    phase_file="$(find "$REPO/$PRIV/roadmap" -maxdepth 1 -type f \
      -name "phase-$(printf '%06d' "$n")-*.md" -print -quit)"
    if [ -n "$phase_file" ]; then
      notify_phase "$phase_file" stalled "" "" "$((STALE_AFTER_SEC / 60))"
    else
      notify "Phase $n looks stalled.

There has been no new output for $STALE_AFTER_SEC seconds. The session is still running; inspect it before stopping the work."
    fi
  fi
}

prune() {
  [ "$DRY_RUN" = 1 ] && return 0
  find "$RUN_DIR" -maxdepth 1 -name 'session-*.log' -mtime "+$LOG_KEEP_DAYS" \
    -delete 2>/dev/null || true
}

heartbeat() {
  [ -n "$HEARTBEAT_URL" ] || return 0
  curl -fsS -m 10 --retry 3 "$HEARTBEAT_URL" >/dev/null 2>&1 \
    || log "heartbeat ping failed ($HEARTBEAT_URL)"
}

coordination_select() {
  # The JSON result is deliberately consumed instead of parsing the legacy
  # tab output. A failed fetch/push must never turn into an unclaimed launch.
  "$PYTHON" "$HARNESS/next_phase.py" --repo "$REPO" --server \
    --machine-id "$PHASE_MACHINE_ID" --json "$@"
}

selection_value() {
  local key="$1"
  "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' \
    "$key"
}

_drive() {
  cd "$REPO"

  if [ "$DRY_RUN" = 1 ]; then
    [ -f "$HALT" ] && { log "dry-run: halted; would refuse to advance"; return 0; }
    tmux has-session -t "$SESSION" 2>/dev/null \
      && { log "dry-run: session '$SESSION' is running; would skip"; return 0; }
    local selection selection_rc=0 state
    selection="$(coordination_select --read-only)" || selection_rc=$?
    if [ "$selection_rc" -ne 0 ] && [ "$selection_rc" -ne 1 ] \
        && [ "$selection_rc" -ne 2 ] && [ "$selection_rc" -ne 3 ]; then
      log "dry-run: coordination unavailable; refusing to launch"
      return 0
    fi
    state="$(printf '%s' "$selection" | selection_value state)"
    case "$state" in
      AVAILABLE)
        local number rel
        number="$(printf '%s' "$selection" | selection_value phase)"
        rel="$(printf '%s' "$selection" | selection_value path)"
        log "dry-run: would reserve and launch phase $number in tmux '$SESSION'"
        printf 'would launch: tmux new-session -d -s %s -x %s -y %s -c %s "bash %s/private/clio-private/harness/phase-driver.sh --session %s %s"\n' \
          "$SESSION" "$TMUX_WIDTH" "$TMUX_HEIGHT" "$REPO" "$REPO" "$number" "$rel"
        ;;
      WAIT_FOR_CLAIM)
        log "dry-run: WAIT_FOR_CLAIM ($(printf '%s' "$selection" | selection_value phase)); no launch"
        ;;
      COORDINATION_INCONSISTENT)
        log "dry-run: coordination state conflicts with completion evidence; no launch"
        ;;
      NO_PHASE)
        log "dry-run: no uncompleted phase"
        ;;
      *)
        log "dry-run: unexpected coordination result '$state'; no launch"
        ;;
    esac
    return 0
  fi

  mkdir -p "$RUN_DIR"

  if [ -f "$HALT" ]; then
    log "halted ($(tr '\n' ' ' <"$HALT")); refusing to advance"
    return 0
  fi

  if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK"
    flock -n 9 || { log "another driver instance holds the lock; skip"; return 0; }
  fi

  if tmux_busy; then
    check_stall
    log "session '$SESSION' is running; skip"
    return 0
  fi

  # No tmux session, but a recorded live PID means an orphaned run (e.g. after
  # `tmux kill-session`, which does not signal the pane). Halt rather than
  # start a second, concurrent run.
  if [ -f "$PIDFILE" ]; then
    local opid
    opid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$opid" ] && kill -0 "$opid" 2>/dev/null; then
      log "orphaned run detected (pid $opid, no session '$SESSION'); halting"
      [ -f "$HALT" ] || printf 'orphaned run pid %s at %s\n' "$opid" "$(ts)" >"$HALT"
      notify "a phase run (pid $opid) is alive but tmux session '$SESSION' is gone (orphaned). Line stopped; investigate."
      return 0
    fi
    rm -f "$PIDFILE"
  fi

  # No live session: clear per-session state a hard kill may have left behind.
  rm -f "$CURRENT" "$STALL"
  prune

  local out rc=0 number rel reservation_id reservation_generation
  if [ "${1:-}" = "--self-test" ]; then
    out="$("$PYTHON" "$HARNESS/next_phase.py" --repo "$REPO")" || rc=$?
    if [ "$rc" -ne 0 ]; then
      log "no uncompleted phase (next_phase rc=$rc)"
      return 0
    fi
    number="${out%%$'\t'*}"; rel="${out#*$'\t'}"
    reservation_id=""; reservation_generation=""
  else
    if ! "$PYTHON" "$HARNESS/gitsync.py" --root "$REPO" --mode start \
        >"$RUN_DIR/coordination-sync.json" 2>/dev/null; then
      log "coordination checkout sync failed; refusing to launch (see $RUN_DIR/coordination-sync.json)"
      return 1
    fi
    local selection selection_rc=0 selection_state
    selection="$(coordination_select)" || selection_rc=$?
    if [ "$selection_rc" -ne 0 ] && [ "$selection_rc" -ne 2 ] \
        && [ "$selection_rc" -ne 3 ]; then
      log "coordination state unavailable; refusing to launch (next_phase rc=$selection_rc)"
      return 1
    fi
    selection_state="$(printf '%s' "$selection" | selection_value state)"
    case "$selection_state" in
      RESERVED)
        number="$(printf '%s' "$selection" | selection_value phase)"
        rel="$(printf '%s' "$selection" | selection_value path)"
        reservation_id="$(printf '%s' "$selection" | selection_value reservation_id)"
        reservation_generation="$(printf '%s' "$selection" | selection_value generation)"
        log "reserved phase $number ($rel) for $PHASE_MACHINE_ID"
        ;;
      WAIT_FOR_CLAIM)
        log "WAIT_FOR_CLAIM for phase $(printf '%s' "$selection" | selection_value phase); no launch"
        return 0
        ;;
      COORDINATION_INCONSISTENT)
        log "coordination state conflicts with completion evidence; no launch"
        return 1
        ;;
      NO_PHASE)
        log "no uncompleted phase"
        return 0
        ;;
      *)
        log "unexpected coordination result '$selection_state'; refusing to launch"
        return 1
        ;;
    esac
  fi
  log "next phase: $number ($rel)"

  local envs=""
  [ -z "${HERMES_PROFILE_NAME:-}" ] || envs="$envs HERMES_PROFILE_NAME='$HERMES_PROFILE_NAME'"
  [ -z "${DISCORD_CHANNEL:-}" ] || envs="$envs DISCORD_CHANNEL='$DISCORD_CHANNEL'"
  [ -z "${DISCORD_FALLBACK_CHANNEL:-}" ] || envs="$envs DISCORD_FALLBACK_CHANNEL='$DISCORD_FALLBACK_CHANNEL'"
  [ -z "${DISABLE_NOTIFY:-}" ] || envs="$envs DISABLE_NOTIFY='$DISABLE_NOTIFY'"
  [ -z "${DISABLE_DISCORD:-}" ] || envs="$envs DISABLE_DISCORD='$DISABLE_DISCORD'"
  [ -z "${DRIVER_STUB_RC:-}" ] || envs="$envs DRIVER_STUB_RC='$DRIVER_STUB_RC'"
  [ -z "${DRIVER_STUB_SLEEP:-}" ] || envs="$envs DRIVER_STUB_SLEEP='$DRIVER_STUB_SLEEP'"
  [ -z "${DRIVER_RUN_DIR:-}" ] || envs="$envs DRIVER_RUN_DIR='$DRIVER_RUN_DIR'"
  [ -z "${CLIO_MACHINE_ID:-}" ] || envs="$envs CLIO_MACHINE_ID='$CLIO_MACHINE_ID'"
  [ -z "${CLIO_PHASE_COORDINATION_BRANCH:-}" ] || envs="$envs CLIO_PHASE_COORDINATION_BRANCH='$CLIO_PHASE_COORDINATION_BRANCH'"
  [ -z "$reservation_id" ] || envs="$envs CLIO_RESERVATION_ID='$reservation_id'"
  [ -z "$reservation_generation" ] || envs="$envs CLIO_RESERVATION_GENERATION='$reservation_generation'"
  local launch="${envs:+$envs }bash '$REPO/$PRIV/harness/phase-driver.sh' --session '$number' '$rel'"

  # Detached geometry: new sessions start at TMUX_WIDTH x TMUX_HEIGHT
  # (defaults 164x48, overridable via .driver.env). runner.py copies the
  # pane size into each harness pty, so opencode inherits it with no
  # second change. This is the initial detached size only: tmux keeps its
  # default window-size policy, so attaching with a smaller terminal may
  # shrink the window, and a session already running keeps its old size
  # until it is relaunched (kill the session or run
  # `tmux resize-window -t <session> -x <w> -y <h>` once).
  9>&- tmux new-session -d -s "$SESSION" -x "$TMUX_WIDTH" -y "$TMUX_HEIGHT" -c "$REPO" "$launch" \
    || { notify "phase $number failed to launch in tmux"; return 1; }
  printf '%s\n' "$number" >"$CURRENT"
  tmux pipe-pane -t "$SESSION" -o "cat >> '$RUN_DIR/session-$number.log'" 2>/dev/null || true
  log "launched phase $number in tmux '$SESSION'"
}

drive() {
  local rc=0
  if command -v flock >/dev/null 2>&1; then
    _drive "${1:-}" || rc=$?
  else
    mkdir -p "$RUN_DIR"
    local portable_lock="$RUN_DIR/driver.lock.d"
    if ! mkdir "$portable_lock" 2>/dev/null; then
      log "another driver instance holds the portable lock; skip"
      heartbeat
      return 0
    fi
    (
      trap 'rmdir "$portable_lock" 2>/dev/null || true' EXIT
      _drive "${1:-}" || rc=$?
      exit "$rc"
    )
    rc=$?
  fi
  heartbeat
  return "$rc"
}

stop() {
  mkdir -p "$RUN_DIR"
  printf 'stopped by operator at %s\n' "$(ts)" >"$HALT"
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux send-keys -t "$SESSION" C-c
    log "stop: sent Ctrl-C to '$SESSION' and wrote halt marker"
  else
    log "stop: wrote halt marker (no live session)"
  fi
}

wait_session_gone() {
  local i=0
  while tmux has-session -t "$SESSION" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -gt 60 ] && break
    sleep 0.25
  done
  sleep 0.3
}

driver_self_test() {
  local fail=0 tmp
  tmp="$(mktemp -d)"
  SESSION="ar-driver-selftest-$$"
  SESSION_NAME="$SESSION"
  DRIVER_RUN_DIR="$tmp/run"
  DISABLE_NOTIFY=1
  DISABLE_DISCORD=1
  DRIVER_STUB_RC=0
  DRIVER_STUB_SLEEP=1
  export SESSION_NAME DRIVER_RUN_DIR DISABLE_NOTIFY DISABLE_DISCORD DRIVER_STUB_RC DRIVER_STUB_SLEEP
  RUN_DIR="$DRIVER_RUN_DIR"
  LOCK="$RUN_DIR/driver.lock"; HALT="$RUN_DIR/halted"
  STALL="$RUN_DIR/stalled"; CURRENT="$RUN_DIR/current"
  PIDFILE="$RUN_DIR/pid"
  NOTIFY_BROKEN="$RUN_DIR/notify-broken"; LOG="$RUN_DIR/driver.log"
  mkdir -p "$RUN_DIR"
  echo "self-test session: $SESSION  state dir: $RUN_DIR"

  drive --self-test || true
  tmux has-session -t "$SESSION" 2>/dev/null \
    && echo "ok: launched a session" || { echo "FAIL: session not launched"; fail=1; }
  geom="$(tmux display-message -p -t "$SESSION" '#{window_width}x#{window_height}' 2>/dev/null || true)"
  [ "$geom" = "${TMUX_WIDTH}x${TMUX_HEIGHT}" ] \
    && echo "ok: geometry $geom" || { echo "FAIL: geometry ${geom:-gone}, want ${TMUX_WIDTH}x${TMUX_HEIGHT}"; fail=1; }
  drive --self-test || true
  grep -q "running; skip" "$LOG" \
    && echo "ok: busy run skipped" || { echo "FAIL: busy run not skipped"; fail=1; }
  sleep 1
  start_count="$(grep -c 'Phase .* started\.' "$LOG" || true)"
  [ "$start_count" = 1 ] \
    && echo "ok: one start notification logged" || { echo "FAIL: expected one start notification, got $start_count"; fail=1; }
  grep -q '\[clio\]' "$LOG" \
    && { echo "FAIL: old notification prefix remains"; fail=1; } \
    || echo "ok: notification prefix removed"

  wait_session_gone
  grep -q "Phase .* has completed\." "$LOG" \
    && echo "ok: completion notification logged" || { echo "FAIL: completion notification missing"; fail=1; }

  # Exercise the stall path without waiting for the real threshold. Use this
  # shell as the live process so the test does not race the short stub run.
  old_stale_after_sec="$STALE_AFTER_SEC"
  stall_test_phase=100000
  printf '%s\n' "$stall_test_phase" >"$CURRENT"
  printf '%s\n' "$$" >"$PIDFILE"
  : >"$RUN_DIR/session-$stall_test_phase.log"
  STALE_AFTER_SEC=0
  sleep 1
  check_stall
  stall_count="$(grep -c 'Phase .* looks stalled\.' "$LOG" || true)"
  [ "$stall_count" = 1 ] && [ -f "$STALL" ] \
    && echo "ok: one stall notification logged" || { echo "FAIL: expected one stall notification, got $stall_count"; fail=1; }
  check_stall
  stall_count_after="$(grep -c 'Phase .* looks stalled\.' "$LOG" || true)"
  [ "$stall_count_after" = "$stall_count" ] \
    && echo "ok: stall notification is not repeated" || { echo "FAIL: stall notification repeated"; fail=1; }
  rm -f "$STALL" "$CURRENT" "$PIDFILE"
  STALE_AFTER_SEC="$old_stale_after_sec"

  DRIVER_STUB_RC=1; export DRIVER_STUB_RC
  rm -f "$HALT"
  drive --self-test || true
  wait_session_gone
  [ -f "$HALT" ] \
    && echo "ok: halt marker written" || { echo "FAIL: halt marker missing"; fail=1; }
  grep -q "Phase .* stopped\." "$LOG" \
    && echo "ok: halt notification logged" || { echo "FAIL: halt notification missing"; fail=1; }

  drive --self-test || true
  grep -q "refusing to advance" "$LOG" \
    && echo "ok: refuses to advance while halted" || { echo "FAIL: advanced while halted"; fail=1; }
  tmux has-session -t "$SESSION" 2>/dev/null \
    && { echo "FAIL: launched a session while halted"; fail=1; }

  # Signal stop: Ctrl-C reaches the trap, which halts and notifies.
  rm -f "$HALT"
  DRIVER_STUB_RC=0; DRIVER_STUB_SLEEP=20; export DRIVER_STUB_RC DRIVER_STUB_SLEEP
  drive --self-test || true
  sleep 0.5
  stop || true
  wait_session_gone
  [ -f "$HALT" ] \
    && echo "ok: stop wrote halt marker" || { echo "FAIL: stop marker missing"; fail=1; }
  grep -q "Phase .* stopped by signal\." "$LOG" \
    && echo "ok: stop notification logged" || { echo "FAIL: stop notification missing"; fail=1; }

  # Coordination failure: the normal driver path must refuse before tmux launch.
  old_repo="$REPO"; old_priv="$PRIV"; old_wf="$WF"; old_harness="$HARNESS"
  old_run_dir="$RUN_DIR"; old_lock="$LOCK"; old_halt="$HALT"; old_stall="$STALL"
  old_current="$CURRENT"; old_pid="$PIDFILE"; old_notify_broken="$NOTIFY_BROKEN"
  old_log="$LOG"; old_session="$SESSION"
  coord_root="$tmp/coordination-failure-root"
  coord_run="$tmp/coordination-failure-run"
  mkdir -p "$coord_root" "$coord_run"
  REPO="$coord_root"; PRIV="private/clio-private"; WF="$coord_run"
  HARNESS="$old_harness"; RUN_DIR="$coord_run"
  LOCK="$RUN_DIR/driver.lock"; HALT="$RUN_DIR/halted"; STALL="$RUN_DIR/stalled"
  CURRENT="$RUN_DIR/current"; PIDFILE="$RUN_DIR/pid"
  NOTIFY_BROKEN="$RUN_DIR/notify-broken"; LOG="$RUN_DIR/driver.log"
  SESSION="ar-driver-coord-failure-$$"
  drive || true
  if grep -q "coordination checkout sync failed" "$LOG" \
      && ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "ok: coordination failure refuses launch"; coord_fail_ok=1
  else
    echo "FAIL: coordination failure did not refuse launch"; coord_fail_ok=0; fail=1
  fi
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  REPO="$old_repo"; PRIV="$old_priv"; WF="$old_wf"; HARNESS="$old_harness"
  RUN_DIR="$old_run_dir"; LOCK="$old_lock"; HALT="$old_halt"; STALL="$old_stall"
  CURRENT="$old_current"; PIDFILE="$old_pid"; NOTIFY_BROKEN="$old_notify_broken"
  LOG="$old_log"; SESSION="$old_session"

  # Orphan: tmux kill-session does not signal the pane, so a live recorded PID
  # with no session must halt instead of starting a second concurrent run.
  rm -f "$HALT"
  drive --self-test || true
  sleep 0.5
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 0.3
  drive --self-test || true
  grep -q "orphaned run detected" "$LOG" \
    && echo "ok: orphan detected" || { echo "FAIL: orphan not detected"; fail=1; }
  [ -f "$HALT" ] \
    && echo "ok: orphan halts the line" || { echo "FAIL: orphan did not halt"; fail=1; }
  [ -f "$PIDFILE" ] && kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true

  tmux kill-session -t "$SESSION" 2>/dev/null || true
  rm -rf "$tmp"
  echo "driver self-test: $([ "$fail" = 0 ] && echo pass || echo FAIL)"
  return "$fail"
}

check() {
  local name bin
  for name in tmux hermes; do
    if bin="$(command -v "$name")"; then echo "$name: $bin"; else echo "$name: MISSING"; fi
  done
  if "$PYTHON" -c 'import yaml' >/dev/null 2>&1; then
    echo "python3: $PYTHON (PyYAML OK)"
  else
    echo "python3: $PYTHON (PyYAML MISSING - runner.py will fail on import)"
  fi
  if command -v flock >/dev/null 2>&1; then
    echo "flock: $(command -v flock)"
  else
    echo "flock: absent (double-start guard falls back to the tmux session check)"
  fi
  if hermes -p "$PROFILE" send --list >/dev/null 2>&1; then
    echo "profile '$PROFILE': usable for send"
  else
    echo "profile '$PROFILE': NOT usable here (need a local Hermes profile with Discord)"
  fi
  [ -f "$WF/.driver.env" ] && echo "env file: present" || echo "env file: none (defaults in use)"
  echo "heartbeat: ${HEARTBEAT_URL:-unset}"
  echo "stall threshold: ${STALE_AFTER_SEC}s"
  echo "tmux geometry: ${TMUX_WIDTH}x${TMUX_HEIGHT} (initial detached size; attaches may resize)"
  "$PYTHON" "$HARNESS/next_phase.py" --self-test
  "$PYTHON" "$HARNESS/phase_reservations.py" --self-test
}

case "${1:-}" in
  --session)
    [ "$#" -eq 3 ] || { echo "usage: phase-driver.sh --session <N> <phase-file>" >&2; exit 2; }
    run_session "$2" "$3"
    ;;
  --check)     check ;;
  --self-test) driver_self_test ;;
  --stop)      stop ;;
  --dry-run)   DRY_RUN=1; drive ;;
  ""|--drive)  drive ;;
  *)
    echo "usage: phase-driver.sh [--dry-run|--check|--self-test|--stop] | --session <N> <phase-file>" >&2
    exit 2
    ;;
esac
