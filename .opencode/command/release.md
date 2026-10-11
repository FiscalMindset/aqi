---
name: release
description: Walk the Dhuan Detective release checklist — gates, changelog, version tag, push to both remotes, and the deploy path.
---

# /release — release checklist

1. **Gate**: run `/verify`. All rows must be green.
2. **Changelog**: move the unreleased section of `CHANGELOG.md` under the new version with today's date.
3. **Version**: `git tag -a vX.Y.Z -m "chore(release): vX.Y.Z"`.
4. **Commit**: `git commit -m "chore(release): vX.Y.Z"` if the changelog changed.
5. **Push both remotes**:
   ```bash
   git push pub main --follow-tags && git push priv main --follow-tags
   ```
6. **CD**: the tag triggers `cd.yml` → staging smoke → manual approval → production canary.
7. **Post-release**: verify smoke output, then update `TODO.md`.

## Never

- Never tag without green gates.
- Never publish a URL you did not observe in real command output.
