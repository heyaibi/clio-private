# Clio private operations.
#
# Run from this directory: `make <target>`.
# Three repositories are managed here:
#   root     the public checkout  (../..)
#   private  this repo            (.)
#   glide    the engine checkout  (./glide, a nested repo)
#
# `make git sync` works: it runs the `git` target (status overview) and then
# the `sync` target. Hyphenated forms (`make git-sync`) do one thing.

ROOT  := $(abspath $(CURDIR)/../..)
PRIV  := $(CURDIR)
GLIDE := $(CURDIR)/glide
RUNS  := $(CURDIR)/runs
RDIR  := $(RUNS)/.driver
DRIVER := $(CURDIR)/scripts/phase-driver.sh
SESSION ?= development
PHASE   ?=
N       ?= 30

.PHONY: help
help:
	@echo "git ......... status overview of all three repos"
	@echo "sync ........ fast-forward pull all three repos (alias: git-sync)"
	@echo "push ........ push all three repos (alias: git-push)"
	@echo "log ......... recent commits in all three repos (N=30 lines, alias: git-log)"
	@echo "check ....... driver environment readiness"
	@echo "dry-run ..... what the driver would do next (no launch)"
	@echo "self-test ... hermetic driver guard/halt/notify test"
	@echo "stop ........ stop the live run (halt + Ctrl-C)"
	@echo "current ..... show live phase, halt, and stall markers"
	@echo "tail ........ last N lines of driver.log (N=30)"
	@echo "next ........ next uncompleted phase (read-only)"
	@echo "clear-halt .. remove halt/stall markers so the line advances"
	@echo "attach ...... attach tmux session read-only (SESSION=development)"
	@echo "cron-show ... show installed driver cron entries"
	@echo "cron-install  install the 10-minute driver entry (quiet 04:00-11:59)"
	@echo "cron-remove . remove the driver cron entry"
	@echo "glide-verify  run the engine test suite"
	@echo "glide-doctor  validate pipeline harness availability"

# --- git across three repos ---

.PHONY: git git-status git-sync sync git-push push git-log log
git: git-status

git-status:
	@echo "== root: $(ROOT)"; git -C "$(ROOT)" status --short | head -10
	@echo "== private: $(PRIV)"; git -C "$(PRIV)" status --short | head -10
	@echo "== glide: $(GLIDE)"; git -C "$(GLIDE)" status --short | head -10

git-sync sync:
	git -C "$(ROOT)" pull --ff-only
	git -C "$(PRIV)" pull --ff-only
	git -C "$(GLIDE)" pull --ff-only

git-push push:
	git -C "$(ROOT)" push
	git -C "$(PRIV)" push
	git -C "$(GLIDE)" push origin main

git-log log:
	@echo "== root"; git -C "$(ROOT)" log --oneline -5
	@echo "== private"; git -C "$(PRIV)" log --oneline -5
	@echo "== glide"; git -C "$(GLIDE)" log --oneline -5

# --- driver ---

.PHONY: check dry-run self-test stop current tail next clear-halt
check:
	bash "$(DRIVER)" --check

dry-run:
	bash "$(DRIVER)" --dry-run

self-test:
	bash "$(DRIVER)" --self-test

stop:
	bash "$(DRIVER)" --stop

current:
	@echo -n "current: "; cat "$(RDIR)/current" 2>/dev/null || echo "(none)"
	@echo -n "halted:  "; tr '\n' ' ' <"$(RDIR)/halted" 2>/dev/null || echo "(none)"
	@echo -n "stalled: "; tr '\n' ' ' <"$(RDIR)/stalled" 2>/dev/null || echo "(none)"

tail:
	tail -$(N) "$(RDIR)/driver.log" 2>/dev/null || echo "no driver.log yet"

next:
	python3 "$(CURDIR)/scripts/pipeline/next_phase.py" --repo "$(ROOT)"

clear-halt:
	rm -f "$(RDIR)/halted" "$(RDIR)/stalled"
	@echo "halt/stall markers cleared; the line advances on the next tick"

# --- tmux ---

.PHONY: attach
attach:
	tmux attach-session -t "$(SESSION)" -r

# --- cron ---

CRON_LINE := */10 0-3,12-23 * * * $(ROOT)/private/clio-private/scripts/phase-driver.sh >> $(RDIR)/.driver-cron.log 2>&1

.PHONY: cron-show cron-install cron-remove
cron-show:
	@crontab -l 2>/dev/null | grep -F "phase-driver.sh" || echo "no driver cron entry"

cron-install:
	@(crontab -l 2>/dev/null | grep -v -F "phase-driver.sh"; echo '$(CRON_LINE)') | crontab -
	@echo "installed:"; crontab -l | grep -F "phase-driver.sh"

cron-remove:
	@crontab -l 2>/dev/null | grep -v -F "phase-driver.sh" | crontab -
	@echo "driver cron entry removed"

# --- engine ---

.PHONY: glide-verify glide-doctor
glide-verify:
	$(MAKE) -C "$(GLIDE)" verify

glide-doctor:
	cd "$(ROOT)" && PYTHONPATH="$(GLIDE)/src" python3 -m glide doctor \
		--pipeline private/clio-private/workflow/pipelines/default.yaml \
		--input phase_number=0 --input phase_file=/dev/null
