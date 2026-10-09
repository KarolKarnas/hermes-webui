# Maintained WebUI fork

This fork is [KarolKarnas/hermes-webui](https://github.com/KarolKarnas/hermes-webui),
with upstream [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui).
The `homelab` branch carries reviewed changes; `master` retains upstream history.
The first release is `homelab-2026-10-09.1`, based on upstream
`e33da25c6cfde3ea337e1b6d7701161d02e995cf`.
Hermes Agent remains a separate upstream dependency, tested with `v2026.9.24`.

## Clarification compatibility fix

That Agent version calls `callback('', None, questions=normalized)` for batches.
The original WebUI accepted keywords but dropped `questions`, producing an empty
question and losing batch answers. This release sends each normalized question
through the existing pending-prompt/wait mechanism and returns answers by `qid`.
Positional batches and legacy single-question callbacks still work. Timeout and
delivery failures return `timed_out` and a notice; cancellation stays distinct.
Questions appear sequentially. Multi-select has no new checkbox interface;
existing choice buttons and free-text responses remain available.

The clarification panel sits 8px above the composer, removing its previous
24px overlap. The stylesheet URL includes a patch query for existing clients.
Refresh after deployment. An expired question must be asked again.

## Contract Routing

This is a compatibility repair in the current execution path. Relevant contracts
are `docs/CONTRACTS.md`, `docs/architecture/agent-api-contract.md`,
`docs/rfcs/webui-run-state-consistency-contract.md`, `docs/UIUX-GUIDE.md`
and `DESIGN.md`. Prompt ownership, session IDs, response waits and cleanup remain
with `api.clarify`. No adapter/RFC migration is introduced.

## Verification

Run the affected and neighboring tests through the isolated repo runner:

```bash
HERMES_HOME=/tmp/hermes-fork-test-agent \
HERMES_WEBUI_STATE_DIR=/tmp/hermes-fork-test-state \
HERMES_WEBUI_TEST_PYTHON=python3.13 \
./scripts/test.sh tests/test_sprint42.py tests/test_clarify_sse.py \
  tests/test_clarify_unblock.py tests/test_4504_clarify_stuck_on_expiry.py \
  tests/test_issue2883_clarify_padding.py tests/test_mobile_layout.py -q
```

The keyword-question regression and timeout assertions fail on the base source.
After the fix, 174 tests and 11 subtests pass with Python 3.13.
The full upstream suite has not been run.

Optional check against an installed Agent checkout, without importing runtime
modules or loading credentials/state:

```bash
python3 scripts/check_clarify_agent_compat.py /path/to/webui /path/to/hermes-agent
```

Five tests execute the actual Agent dispatcher and extracted WebUI bridge with
inert prompt waits. They cover answers, timeout, cancellation, undelivered prompts
and both legacy callback shapes. This is protocol evidence, not proof of a real
model/browser conversation.

Browser tooling belongs in an isolated development directory:

```bash
npm install --prefix /tmp/hermes-layout-deps playwright@1.64.0
/tmp/hermes-layout-deps/node_modules/.bin/playwright install chromium
NODE_PATH=/tmp/hermes-layout-deps/node_modules \
  node scripts/check_clarify_layout.cjs /tmp/hermes-layout-evidence
```

Set `CHROME_PATH` to use an existing Chromium/Chrome binary. The script uses real
CSS and clarification markup with synthetic questions. It compares base and fixed
geometry, checks free-text input and scrolling long questions, and saves images.
The reduced viewport approximates space with a keyboard; actual Android keyboard
and PWA lifecycle behavior remain unverified. Before/after evidence:

| Viewport | Before | After |
| --- | --- | --- |
| Desktop 1280×800 | [Before](evidence/clarify-compat/before-1280x800.png) | [After](evidence/clarify-compat/after-1280x800.png) |
| Narrow 720×800 | [Before](evidence/clarify-compat/before-720x800.png) | [After](evidence/clarify-compat/after-720x800.png) |
| Phone 390×844 | [Before](evidence/clarify-compat/before-390x844.png) | [After](evidence/clarify-compat/after-390x844.png) |
| Reduced 390×440 | [Before](evidence/clarify-compat/before-390x440.png) | [After](evidence/clarify-compat/after-390x440.png) |

The `Homelab regression checks` GitHub workflow repeats the focused Python
suite, changed-line lint and browser geometry checks on `homelab`.

## Updating and releasing

Configure `origin` for this fork and `upstream` for its parent. Fetching upstream
does not authorize deployment or upgrading dependencies. Keep existing release
tags immutable and avoid force-pushing shared branches.

```bash
git fetch upstream
git switch homelab
git merge upstream/master
# Resolve conflicts and run affected/neighboring tests and browser checks.
git push origin homelab
```

Review Agent/WebUI callback compatibility on every version change. Retire fixes
when upstream implements their behavior. Record new pins and create an annotated
`homelab-YYYY-MM-DD.N` tag only after tests pass. Install its exact commit in a new
source directory, with runtime state and credentials outside the checkout.
Verify every live session is idle with no pending action before switching the
source symlink and restarting. Keep the previous source release for rollback;
verify health, authenticated access and session continuity after switching.
Do not run development tests against production state.
