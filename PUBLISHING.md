# Publishing

This monorepo ships two packages. Both are MIT-licensed and published manually for now.

## TypeScript: `@langchain/ceki` → npm

Requires: npm Automation token (`npm_...`) with publish access to `@langchain/ceki`. **Automation** tokens bypass 2FA — do not use a Classic Publish or Granular token for CI.

```bash
cd packages/ts
npm install
npm run build
npm run test

# Force IPv4 — the lab environment IPv6 path to registry.npmjs.org is flaky.
NODE_OPTIONS="--dns-result-order=ipv4first" npm publish --access public
```

When the `Ceki-me/ceki-langchain` GitHub repo is created and the `NPM_TOKEN` secret is set, pushing a release tag triggers `.github/workflows/publish.yml` which performs the same publish in CI.

## Python: `langchain-ceki` → PyPI

Requires: PyPI account with a project-scoped API token (`__token__` username + `pypi-...` password).

```bash
cd packages/python
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

## Pre-publish checklist

- [ ] Bump version in `packages/ts/package.json` AND `packages/python/pyproject.toml`
- [ ] Update CHANGELOG (root) and per-package CHANGELOG if applicable
- [ ] `npm run build && npm run test` in `packages/ts` — green
- [ ] `python -m pytest tests/` in `packages/python` — green
- [ ] Leak check: `grep -rniE "clawapi|clawed|ittribe|/home/node|codename" .` — no hits
- [ ] Tag `vX.Y.Z` in git, push tag
- [ ] Create GitHub Release — the publish workflow runs on `release: published`
- [ ] Verify on the registry: `npm view @langchain/ceki@X.Y.Z`, `pip index versions langchain-ceki`
