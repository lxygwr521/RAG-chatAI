---
name: problem-log
description: >
  This skill should be used when the user BOTH (a) raises a problem or issue about the
  current project AND (b) asks for a solution, analysis, or fix.  When triggered, record
  the problem description and the final solution/conclusion as a Markdown file under the
  project's problem/ directory.  Do NOT trigger on questions that are purely informational
  ("how does X work?") or on feature requests that don't identify a specific problem.
---

# Problem Log Skill

Record project problems and their solutions as timestamped Markdown files under
`problem/` in the project root.

## Trigger Condition

Trigger this skill when the user's message satisfies BOTH:

1. **Identifies a problem** — describes something wrong, broken, misaligned, risky,
   or suboptimal in the current project (code, architecture, workflow, dependencies, etc.).
2. **Requests action** — asks for a solution, fix, analysis, recommendation, or plan to
   address the problem.

**Do NOT trigger** on:
- Pure information questions ("How does the RAG pipeline work?")
- Feature requests without a problem statement ("Add a logout button")
- General chat or status updates

## Procedure

1. After the problem has been analyzed and the solution has been provided (i.e., at the
   end of the turn once the user has the answer), save a record to the `problem/` directory.
2. Create the `problem/` directory at the project root if it does not exist.
3. Write a Markdown file with a name that reflects the problem itself — a short
   English/kebab-case slug summarizing the issue (e.g. `eval-agent-pipeline-misalignment.md`,
   `missing-rag-citations-event.md`). The filename should make the problem recognizable
   at a glance without opening the file.

### File Template

```markdown
---
date: <ISO timestamp of when the problem was raised>
status: resolved | open | deferred
severity: high | medium | low
tags: [<relevant tags, e.g. evaluation, RAG, agent>]
---

# <Short title summarizing the problem>

## Problem

<Detailed description of the problem — what was observed, why it matters, how it
was discovered, and any relevant context (files, lines, data flow).>

## Solution

<The solution or conclusion that was provided. Include concrete changes made
(file paths, rationale), decisions taken, and any trade-offs noted. If the
solution is deferred or partial, note what remains.>
```

### Writing Guidelines

- Use the same language (Chinese or English) as the user's problem statement.
- The **Problem** section should be self-contained — a reader weeks later should
  understand the context without reading the original conversation.
- The **Solution** section should be actionable and concrete, not vague.
- Link to relevant source files with relative paths (e.g. `[runner.py](server/evaluation/runner.py#L109-L125)`).
- Keep each file focused on a single problem-solution pair.
