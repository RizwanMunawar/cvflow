# Releasing CVFlow

CVFlow publishes to PyPI automatically when a GitHub **Release** is published,
using **PyPI Trusted Publishing (OIDC)**. No API token or secret is stored in
the repository — GitHub proves the workflow's identity to PyPI directly.

The workflow lives at [`.github/workflows/publish.yml`](../.github/workflows/publish.yml).

## One-time setup (on PyPI)

Do this once, before the first release. Because the `cvflow` project doesn't
exist on PyPI yet, you register a **pending publisher**:

1. Sign in at <https://pypi.org> → **Your account** → **Publishing**
   (<https://pypi.org/manage/account/publishing/>).
2. Under **Add a new pending publisher**, choose **GitHub** and enter:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `cvflow` |
   | Owner | `RizwanMunawar` |
   | Repository name | `cvflow` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

3. Save. The first successful publish creates the project and binds it to this
   publisher; the "pending" publisher becomes a normal one.

> **Check the name first.** If `cvflow` is already taken on PyPI, pick a
> distribution name that's free (e.g. `cvflow-cli`), update `name` in
> `pyproject.toml` and the two `cvflow` references above, and register that
> instead. The import name (`import cvflow`) can stay the same.

Optionally add a matching **`pypi` environment** under the repo's
**Settings → Environments** if you want required reviewers or a wait timer
before a publish runs.

## Cutting a release

1. Bump `version` in `pyproject.toml` (semantic versioning).
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under the new version.
3. Commit, open a PR, merge to `main`.
4. Tag and publish a GitHub Release for that version (e.g. tag `v0.2.0`).
   Publishing the release triggers the workflow.
5. Watch the **Actions** tab: the `build` job builds and checks the sdist +
   wheel, then `publish` uploads them to PyPI via OIDC.

You can also run the workflow manually from the **Actions** tab
(**workflow_dispatch**) to build and publish the current `main`.

## Testing against TestPyPI (optional)

To rehearse without touching real PyPI, register the same pending publisher on
<https://test.pypi.org> and add a `repository-url` to the publish step:

```yaml
      - name: Publish to TestPyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
```
