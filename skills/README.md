# Custom Agent Skills

This directory hosts opt-in skills for AI coding agents working on this
repository. Skills live as self-contained directories with a top-level
`SKILL.md` (markdown with YAML front matter) and an optional
`references/` folder for longer reference material.

## Available skills

- [`greploop/`](greploop/SKILL.md) — Iteratively trigger Greptile reviews
  on a PR/MR/CL, address every actionable comment, push fixes, resolve
  threads, and repeat until Greptile gives a 5/5 confidence score with
  zero unresolved comments.
- [`check-pr/`](check-pr/SKILL.md) — One-shot audit of a PR/MR/CL for
  unresolved comments, failing status checks, and incomplete
  descriptions. Useful as the first step inside a `greploop` cycle or as
  a standalone PR readiness check.

Both skills are vendored from the upstream
[greptileai/skills](https://github.com/greptileai/skills) repository
under the MIT licence kept in [`LICENSE`](LICENSE). Updates can be
pulled in by re-running:

```bash
git clone --depth=1 https://github.com/greptileai/skills.git /tmp/greptile-skills
cp -r /tmp/greptile-skills/greploop skills/
cp -r /tmp/greptile-skills/check-pr skills/
cp /tmp/greptile-skills/LICENSE skills/LICENSE
```

## Using a skill

Skills are plain markdown — read `skills/<name>/SKILL.md` and follow the
instructions step by step. They do not require any installation; they
are picked up by agents that look for `SKILL.md` files in this
directory (Devin, Cursor, Codex, etc.).

When a skill grants tool permissions via the `allowed-tools` front
matter, any tool not listed there is out of scope for that skill.
