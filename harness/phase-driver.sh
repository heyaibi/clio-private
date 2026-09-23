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
# HEARTBEAT_URL, STALE_AFTER_SEC, LOG_KEEP_DAYS.
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
    timeout 20 hermes -p "$PROFILE" send --to "$1" "[clio] $2" </dev/null >>"$LOG" 2>&1
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout 20 hermes -p "$PROFILE" send --to "$1" "[clio] $2" </dev/null >>"$LOG" 2>&1
  else
    hermes -p "$PROFILE" send --to "$1" "[clio] $2" </dev/null >>"$LOG" 2>&1
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
    notify "phase $CUR_PHASE STOPPED by signal (rc=$rc). Line stopped; clear $HALT to resume."
  fi
  rm -f "$CURRENT" "$PIDFILE"
  exit "$rc"
}

run_session() {
  local number="$1" rel="$2" rc=0 state
  CUR_PHASE="$number"
  mkdir -p "$RUN_DIR"
  trap 'on_stop 129' HUP
  trap 'on_stop 130' INT
  trap 'on_stop 143' TERM
  printf '%s\n' "$$" >"$PIDFILE"
  cd "$REPO"
  notify "phase $number starting ($rel)"
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
    0)   notify "phase $number finished: ${state:-completed}" ;;
    130) notify "phase $number interrupted; will resume on the next tick" ;;
    *)   printf 'phase %s rc=%s state=%s at %s\n' \
           "$number" "$rc" "${state:-unknown}" "$(ts)" >"$HALT"
          notify "phase $number HALTED: ${state:-exit $rc}. Line stopped; see $PRIV/runs/phase-$(printf '%06d' "$number")/" ;;
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
  local n phase_dir newest now age
  n="$(cat "$CURRENT" 2>/dev/null || true)"
  [ -n "$n" ] || return 0
  phase_dir="$WF/phase-$(printf '%06d' "$n")"
  newest="$(newest_mtime "$RUN_DIR/session-$n.log" "$phase_dir"/*)"
  [ "$newest" -gt 0 ] || return 0
  now="$(date +%s)"; age=$((now - newest))
  if [ "$age" -gt "$STALE_AFTER_SEC" ]; then
    printf 'stalled: phase %s no output for %ss at %s\n' \
      "$n" "$age" "$(ts)" >"$STALL"
    notify "phase $n looks STALLED (no output for $((age / 60)) min). Session still running; inspect it."
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

_drive() {
  cd "$REPO"

  if [ "$DRY_RUN" = 1 ]; then
    [ -f "$HALT" ] && { log "dry-run: halted; would refuse to advance"; return 0; }
    tmux has-session -t "$SESSION" 2>/dev/null \
      && { log "dry-run: session '$SESSION' is running; would skip"; return 0; }
    local out
    if ! out="$("$PYTHON" "$HARNESS/next_phase.py" --repo "$REPO")"; then
      log "dry-run: no uncompleted phase"
      return 0
    fi
    local number="${out%%$'\t'*}" rel="${out#*$'\t'}"
    log "dry-run: would launch phase $number in tmux '$SESSION'"
    printf 'would launch: tmux new-session -d -s %s -c %s "bash %s/private/clio-private/harness/phase-driver.sh --session %s %s"\n' \
      "$SESSION" "$REPO" "$REPO" "$number" "$rel"
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

  local out rc=0
  out="$("$PYTHON" "$HARNESS/next_phase.py" --repo "$REPO")" || rc=$?
  if [ "$rc" -ne 0 ]; then
    log "no uncompleted phase (next_phase rc=$rc)"
    return 0
  fi
  local number="${out%%$'\t'*}" rel="${out#*$'\t'}"
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
  local launch="${envs:+$envs }bash '$REPO/$PRIV/harness/phase-driver.sh' --session '$number' '$rel'"

  9>&- tmux new-session -d -s "$SESSION" -c "$REPO" "$launch" \
    || { notify "phase $number failed to launch in tmux"; return 1; }
  printf '%s\n' "$number" >"$CURRENT"
  tmux pipe-pane -t "$SESSION" -o "cat >> '$RUN_DIR/session-$number.log'" 2>/dev/null || true
  log "launched phase $number in tmux '$SESSION'"
}

drive() {
  local rc=0
  _drive || rc=$?
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

  drive || true
  tmux has-session -t "$SESSION" 2>/dev/null \
    && echo "ok: launched a session" || { echo "FAIL: session not launched"; fail=1; }
  drive || true
  grep -q "running; skip" "$LOG" \
    && echo "ok: busy run skipped" || { echo "FAIL: busy run not skipped"; fail=1; }
  wait_session_gone
  grep -q "finished: completed" "$LOG" \
    && echo "ok: end notification logged" || { echo "FAIL: end notification missing"; fail=1; }

  DRIVER_STUB_RC=1; export DRIVER_STUB_RC
  rm -f "$HALT"
  drive || true
  wait_session_gone
  [ -f "$HALT" ] \
    && echo "ok: halt marker written" || { echo "FAIL: halt marker missing"; fail=1; }
  grep -q "HALTED" "$LOG" \
    && echo "ok: halt notification logged" || { echo "FAIL: halt notification missing"; fail=1; }

  drive || true
  grep -q "refusing to advance" "$LOG" \
    && echo "ok: refuses to advance while halted" || { echo "FAIL: advanced while halted"; fail=1; }
  tmux has-session -t "$SESSION" 2>/dev/null \
    && { echo "FAIL: launched a session while halted"; fail=1; }

  # Signal stop: Ctrl-C reaches the trap, which halts and notifies.
  rm -f "$HALT"
  DRIVER_STUB_RC=0; DRIVER_STUB_SLEEP=20; export DRIVER_STUB_RC DRIVER_STUB_SLEEP
  drive || true
  sleep 0.5
  stop || true
  wait_session_gone
  [ -f "$HALT" ] \
    && echo "ok: stop wrote halt marker" || { echo "FAIL: stop marker missing"; fail=1; }
  grep -q "STOPPED by signal" "$LOG" \
    && echo "ok: stop notification logged" || { echo "FAIL: stop notification missing"; fail=1; }

  # Orphan: tmux kill-session does not signal the pane, so a live recorded PID
  # with no session must halt instead of starting a second concurrent run.
  rm -f "$HALT"
  drive || true
  sleep 0.5
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 0.3
  drive || true
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
  "$PYTHON" "$HARNESS/next_phase.py" --self-test
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
