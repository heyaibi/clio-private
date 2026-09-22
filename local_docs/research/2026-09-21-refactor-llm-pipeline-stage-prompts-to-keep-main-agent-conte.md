# Research: Refactor LLM pipeline stage prompts to keep main agent context low via ephemeral spawn-delegate-die subagents

Generated: 2026-09-21 18:19 UTC+05:30  *  Mode: flat  *  Sources: 13

## Summary

Give each subagent its own context window so it explores in parallel and returns only condensed findings to the lead agent[1]. Claude Code runs each subagent in its own context window and delegates matching tasks to it, which works independently and returns only results[4]. Keep the orchestrator prompt lean by making it own only planning, delegation-prompt writing, dispatch, and result evaluation while workers do all execution work[6]. Supervise isolated subagents with context quarantine so workers share no state and the main agent integrates only final results[9]. Gate pull requests on diff and patch coverage instead of re-running full project coverage gates[11].

## What proven patterns keep orchestrator main agent context window low in multi-agent LLM pipelines?

- Give each subagent its own context window so it explores in parallel and returns only condensed findings to the lead agent[1].
  > Subagents facilitate compression by operating in parallel with their own context windows, exploring different aspects of the question simultaneously before condensing the most important tokens for the lead research agent.
- Delegate side work that would flood the main conversation to a subagent that works in its own context and returns only a summary[2].
  > Use one when a side task would flood your main conversation with search results, logs, or file contents you won't reference again: the subagent does that work in its own context and returns only the summary.
- Keep one manager agent owning the final answer while specialist agents handle bounded subtasks via tools or handoffs[3].
  > A manager agent keeps control of the conversation and calls specialist agents through Agent.as_tool().

## How do ephemeral spawn-delegate-die subagents work in Claude Code OpenCode and similar harnesses?

- Claude Code runs each subagent in its own context window and delegates matching tasks to it, which works independently and returns only results[4].
  > When Claude encounters a task that matches a subagent’s description, it delegates to that subagent, which works independently and returns results.
- OpenCode lets primary agents automatically invoke subagents for specialized tasks, or users manually invoke them with @ mentions[5].
  > Subagents are specialized assistants that primary agents can invoke for specific tasks.

## What are best practices for splitting large prompt files into lean orchestrator prompts plus detailed worker prompts?

- Keep the orchestrator prompt lean by making it own only planning, delegation-prompt writing, dispatch, and result evaluation while workers do all execution work[6].
  > It reads the task, decides how to decompose it, writes the delegation prompts, dispatches workers, evaluates what comes back, and decides whether to iterate, escalate, or finish.
- Give each worker prompt only three things: a task-scoped system prompt, the minimum necessary context, and a strict expected output format[7].
  > The orchestrator creates a subagent with three things: a system prompt scoped to the specific task, the minimum necessary context, and an expected output format.
- Isolate each worker with its own clean context, prompt, tool subset, and scratch space so workers do not pollute each other or the orchestrator[8].
  > Justified where each sub-task benefits from a clean context (its own prompt, tool subset, and scratch space) so workers do not pollute each other or the orchestrator.

## How to enforce disjoint file ownership and safe integration when parallel subagents edit code?

- Supervise isolated subagents with context quarantine so workers share no state and the main agent integrates only final results[9].
  > Subagents isolate this detailed work—the main agent receives only the final result, not the dozens of tool calls that produced it.
- Decompose parallel work into focused stateless subtasks owned by independent subagents and merge their returned summaries centrally[10].
  > A subagent is an independent AI agent that performs focused work, such as researching a topic, analyzing code, or reviewing changes, and reports the results back to the main agent.

## What verification patterns avoid repeated full test coverage gates while keeping per-file guarantees?

- Gate pull requests on diff and patch coverage instead of re-running full project coverage gates[11].
  > By default, Codecov will gate and report on coverage changes on Git diff in the Pull request; with overall project coverage reporting available on the Codecov dashboard.
- Use --changedSince to run only tests related to changes since a branch or commit[12].
  > Runs tests related to the changes since the provided branch or commit hash.
- Use affected commands to run tasks only on projects impacted by a pull request instead of re-testing everything[13].
  > As your workspace grows, re-testing, re-building, and re-linting all projects becomes too slow.

## Sources

1. [How we built our multi-agent research system | Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
2. [Create custom subagents](https://code.claude.com/docs/en/sub-agents.md)
3. [Agent orchestration - OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/)
4. [Create custom subagents - Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
5. [Agents | OpenCode](https://opencode.ai/docs/agents/)
6. [The Orchestrator-Worker Pattern for AI Coding Agents](https://www.learninternetgrow.com/orchestrator-worker-pattern/)
7. [The Orchestrator Pattern (Agent) — Prompt Engines Lab](https://www.promptengines.com/labnotes/articles/2026-03-14-orchestrator-pattern-agent-design-v3.html)
8. [Orchestrator-Workers | detached-node](https://detached-node.dev/agentic-design-patterns/orchestrator-workers)
9. [Subagents - Docs by LangChain](https://docs.langchain.com/oss/python/deepagents/subagents)
10. [Use subagents in Visual Studio Code](https://code.visualstudio.com/docs/agents/run/subagents)
11. [Quick Start](https://docs.codecov.com/docs/quick-start)
12. [Jest CLI Options · Jest](https://jestjs.io/docs/cli)
13. [Run Only Tasks Affected by a PR | Nx](https://nx.dev/docs/features/ci-features/affected)
