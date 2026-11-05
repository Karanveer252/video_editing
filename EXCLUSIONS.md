# EXCLUSIONS (from /workspace/skills/phone-to-ad-video/)

| Path | Why |
|------|-----|
| `.venv/` | Local Python env (~843 MB); not skill source |
| `research/_src/` | Reference clones (~103 MB); STATUS said leave out of any repo |
| `test-output/` | Test renders/sheets (~435 MB); not for publish |
| `render/node_modules` | Symlink to another build tree; recreate with npm install |
| `scripts/__pycache__/`, `tests/__pycache__/` | Bytecode |
| `.handoff/` | Session working notes (`claude_task.md`, `claude_run.log`) |
| `.git/` | None in source |
| `.env` / secrets | None found outside excluded trees |

Kept: `research/EXTRACTION.md` only under research/.
