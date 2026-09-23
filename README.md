AI agents should refrain from refactoring this file without first explicity obtaining approval from the operator.

===

Run this command both locally and in the remote server.

```bash
git config --global --get core.excludesfile || echo "${XDG_CONFIG_HOME:-$HOME/.config}/git/ignore"
```

Manually copy over the contents of the local excludes file to remote.

===

```bash
git clone https://github.com/heyaibi/clio
cd clio
mkdir private
cd private
git clone https://github.com/heyaibi/clio-private
```



```bash
tmux attach -t development

cd ~/clio

python3 private/clio-private/harness/next_phase.py
bash private/clio-private/harness/phase-driver.sh --check
bash private/clio-private/harness/phase-driver.sh --dry-run
bash private/clio-private/harness/phase-driver.sh --self-test


bash private/clio-private/harness/phase-driver.sh && tmux attach -t development
```
