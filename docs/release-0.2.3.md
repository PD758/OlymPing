# Release 0.2.3

Personal calendar views now exclude olympiads the current user marked «Не интересно».
This applies to Today, 7 days, 30 days and Open registration. Existing topic, whole-group,
grade and source filters still apply; another user's interest selections do not affect
the result. Matching events can appear without a pre-existing subscription. Ignored
events remain accessible in the filtered full catalog so the user can change their mind.

List limits now apply after personal filtering. Open registration is ordered by deadline
before truncating; hidden events no longer consume the available positions in either list.

Validation: 84 tests passed, including actor isolation, all three date windows, ignored
events, subject and whole-group matching, restoring interest, and filtering before limits.
Ruff, mypy and Pyright passed; the frozen-lock Docker image built successfully.

This changes application logic, so the release is 0.2.3. The preceding law/economics/
financial-security calendar update was committed separately without a version bump.
No schema migration is needed. Deploy with the existing database volume after pulling
and rebuilding the application image.
