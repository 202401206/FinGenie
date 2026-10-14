# Contributing

Start with `docs/setup.md`. Work in the directory owned by your team and keep PRs
small enough for another student to understand. A PR (pull request) asks teammates
to review changes before they are merged into the shared branch.

## Initial repository creation (team leader, once)

No Git repository, remote, commit or GitHub repository was created by the scaffold.
From `FinGenie/`, when you are ready:

```sh
git init -b main
git status --short
```

After completing the README's pre-commit checks, stage intended files, inspect
them, and commit yourself:

```sh
git add .
git diff --cached
git commit -m "chore: establish FinGenie foundation"
```

Create an empty GitHub repository (without a generated README), then use its actual
remote URL with `git remote add origin YOUR_REPOSITORY_URL` and `git push -u origin main`.
Those commands publish your work; review staged contents first.

## Normal feature work

```sh
git switch main
git pull --ff-only origin main
git switch -c feat/upload-validation
```

Branches: `feat/short-description`, `fix/short-description`,
`docs/short-description`, `chore/short-description`.
Commits: `feat: validate CSV headers`, `fix: preserve source rows`,
`docs: explain parser fixtures`, `chore: update lint settings`.

While on your feature branch, keep it current:

```sh
git fetch origin
git merge origin/main
```

If there are conflicts, inspect the marked files, agree the intended behavior,
edit them, run checks, then stage and commit the resolution. Ask a teammate when
uncertain. Avoid force-pushing shared branches. Start updates with a clean working
tree; commit your current work or use a separate branch first.

Stage specific files, inspect the diff, then publish the branch:

```sh
git add path/to/changed-file
git diff --cached
git commit -m "feat: describe the change"
git push -u origin feat/upload-validation
```

On GitHub open a PR into `main`, fill the template, link the task and request a
reviewer. A teammate other than the author reviews before merging. Keep the
description focused on behavior and validation. Use the normal GitHub merge UI;
there is no special release or branching workflow.

## Shared contracts

Backend + Frontend review endpoint changes. Backend + AI + Analysis review parsed
data and result schemas; include Frontend if it consumes them. Update examples,
docs and affected code together. See `docs/team-ownership.md` for ownership.

## Definition of done

- User-story acceptance criteria met, within the intended sprint scope.
- Relevant tests and lint/format checks pass; limitations are stated in the PR.
- Backend logic has meaningful tests, including financial edge cases when added.
- Financial numbers are traceable and unknown inputs are handled explicitly.
- No secrets or personal financial data; docs and contracts stay consistent.
- Another teammate reviewed, affected teams approved shared changes, PR merged.

## Protect main manually

The team leader can open GitHub repository **Settings -> Branches / Rulesets** and
add a rule targeting `main`: require pull requests and at least one approval,
resolve review conversations, and prevent force pushes/deletions. If automated
checks are added later, require their real status names after they run. No CI
workflow or branch protection has been configured by this scaffold. Repository
permissions and available rule options depend on the GitHub plan.
