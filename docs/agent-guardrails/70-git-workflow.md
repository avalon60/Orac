# Git Workflow

## Purpose

This document defines repository workflow guardrails for git state, staged
changes, commits, branches, pushes, pull requests, and generated artifacts.

These rules apply to agent behaviour around repository change management. They
do not replace project-specific branch, commit, or release policies.

## Working tree awareness

Before staging, committing, branching, pushing, or opening a pull request, check
the working tree state.

Treat existing uncommitted changes as user-owned unless there is clear evidence
that the agent made them during the current task.

Do not revert, overwrite, move, delete, stage, or commit user-owned changes
unless the user explicitly requests that action.

If user-owned changes are in files relevant to the current task, work with them
carefully and mention the overlap before taking git actions.

## New files

Creating a new file during the current task requires an explicit staging
decision from the user.

If the agent creates one or more new files, it must list those files and ask the
user which of them, if any, should be staged. Ask after creating the cohesive
set of new files and before continuing into unrelated work, before the final
response, and before any git action, whichever comes first.

Ask once for the set of newly created files, rather than asking separately for
each file.

Do not stage newly created files unless the user explicitly confirms that they
should be staged.

This rule applies even when the user asks to stage changes, prepare a commit, or
commit the current work. The user may still choose to stage all, some, or none
of the new files.

Do not treat leaving new files unstaged as a reason to skip the question. The
question is required because the files were created, not because staging has
already begun.

Do not interpret this rule as applying only when the agent is about to run
`git add`. The staging decision belongs to the user once new files exist.

## Modified files

When the user asks to stage changes, prepare a commit, or create a commit,
staging modified existing files is allowed only for files that are in scope for
the current task.

Report the staged file list before committing when practical.

Do not stage unrelated modified files to make the working tree look clean.

## Generated and temporary files

Treat generated files, exports, logs, build outputs, archives, screenshots,
coverage output, local caches, and temporary artifacts as not staged by default.

Stage generated artifacts only when the user explicitly requests them or
confirms that they are intended deliverables.

If a generated artifact is required for the repository to function, mention why
it should be included before asking for confirmation.

## Commits

Do not create a commit unless the user explicitly asks for one.

Before committing, verify that the staged changes match the intended scope.

Commit messages should describe the change plainly and should not rely on
branch names or external context to explain the work.

## Logical commit bundling

Group changes into commits by intent.

A commit should normally represent one reviewable reason for change, such as a
bug fix, a feature slice, a documentation update, a test addition, or a
supporting scaffold update.

Do not combine unrelated concerns in one commit merely because they were made
during the same session.

Keep generated artifacts with the source or configuration change that requires
them when they are intended repository deliverables.

Separate mechanical formatting, renames, or broad generated updates from
behavioural changes when that separation would make review safer or clearer.

If the user asks for a commit and the current work naturally splits into
multiple logical commits, explain the proposed grouping and ask before creating
multiple commits.

If the desired grouping is ambiguous, ask before committing.

## Branches, pushes, and pull requests

Do not create or switch branches, push changes, or open pull requests unless the
user explicitly asks for that action.

Before pushing or opening a pull request, confirm the target branch and the
change scope when either is ambiguous.

Do not push unrelated local changes.

## Final reporting

When git actions were taken, report what changed and which files were staged,
committed, pushed, or included in a pull request.

When git actions were intentionally skipped because confirmation was required,
say so clearly.
