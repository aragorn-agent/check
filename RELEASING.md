# Releasing

Both registries are published from GitHub Actions with **trusted publishing** (OIDC). No long-lived registry token is stored in this repository or on a maintainer's machine.

The workflow is [.github/workflows/publish.yml](.github/workflows/publish.yml). It runs on a published GitHub Release and can also be started by hand from the Actions tab.

## One-time setup

### PyPI

1. Sign in at https://pypi.org/manage/account/publishing/.
2. Add a **pending publisher** with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `agentapiai-check` |
   | Owner | `aragorn-agent` |
   | Repository name | `check` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

3. Save. The first successful publish claims the project name.

### npm

1. Sign in at https://www.npmjs.com.
2. Open the trusted publisher settings for the package name `agentapiai-check` (npm allows configuring a publisher before the first publish; the first publish must follow within 2 days of saving).
3. Use these values:

   | Field | Value |
   | --- | --- |
   | Publisher | GitHub Actions |
   | Organization or user | `aragorn-agent` |
   | Repository | `check` |
   | Workflow filename | `publish.yml` |
   | Environment name | leave empty |
   | Allowed actions | allow `npm publish` (and `npm stage publish`) |

Requirements: npm CLI 11.5.1+ and Node 22.14+. The workflow installs `npm@11` and uses Node 22 on GitHub-hosted runners.

## Cutting a release

1. Bump the version in **both** places, keeping them equal:
   - `pyproject.toml` → `version`
   - `packages/node/package.json` → `version`
2. Add a `CHANGELOG.md` entry.
3. Run the tests: `python -m unittest discover -s tests -v`.
4. Commit, tag, push:

   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

5. Create a GitHub Release from the tag with the changelog section as its body. Publishing the release starts the workflow; both registries receive the same version.

## If trusted publishing is unavailable

Fallbacks, in order of preference:

- **PyPI**: create an API token scoped to the project and store it as `PYPI_API_TOKEN`; add `password: ${{ secrets.PYPI_API_TOKEN }}` to the publish step.
- **npm**: create a granular access token with publish rights and store it as `NPM_TOKEN`; add `env: NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}` to the npm job.

Never commit either token. Remove the fallback once trusted publishing works.

## Verifying

```bash
python -m pip download agentapiai-check==X.Y.Z --no-deps -d /tmp/check
npx agentapiai-check@X.Y.Z --help
```

Both commands should run without a token.
