# Local verification

Run from the repository root with Python 3:

```sh
python -m unittest discover -s tests -p 'test_*.py'
python scripts/verify.py
git diff --check
```

Run these checks before requesting Draft PR review.

The unit test command reports whether the current tests pass. The verifier reports whether its repository checks pass. `git diff --check` checks tracked changes for whitespace errors. These results do not establish the accuracy of research claims or authorize publication.

On Windows, the `python` command may point to an app alias without an installed interpreter. If so, install Python 3 or use the full path to a working Python 3 executable in the first two commands.
