# Publishing

This monorepo ships two packages. Both are MIT-licensed and published manually for now.

## TypeScript: `@langchain/ceki` → npm

Requires: npm account with publish access to `@langchain` scope OR (if scope not granted) republish under `@ceki/langchain-ceki` namespace.

```bash
cd packages/ts
npm install
npm run build
npm run test
npm publish --access public
```

## Python: `langchain-ceki` → PyPI

Requires: PyPI account with API token (`__token__` username + `pypi-...` password).

```bash
cd packages/python
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

## Pre-publish checklist

- [ ] Bump version in `package.json` (TS) and `pyproject.toml` (Python)
- [ ] Update CHANGELOG.md
- [ ] Run tests on both packages
- [ ] Tag `vX.Y.Z` in git, push tag
- [ ] Publish to npm + PyPI
- [ ] Open GitHub Release with notes
