# Ponytail-style development rules

When modifying this repository, follow these rules:

1. Prefer deleting code over adding code.
2. Before writing custom code, check whether the same result can be achieved with:
   - standard library features,
   - native framework/platform APIs,
   - existing project utilities,
   - existing dependencies.
3. Do not introduce new abstractions unless they remove real duplication or isolate real complexity.
4. Avoid unnecessary managers, factories, wrappers, registries, adapters, and helper layers.
5. Keep diffs small and behavior-preserving.
6. Do not add dependencies unless there is a clear maintenance or security benefit.
7. Do not remove security checks, validation at trust boundaries, accessibility behavior, audit logging, data-loss protection, or error handling required for correctness.
8. For every change, explain:
   - what was deleted or simplified,
   - why the simpler version is safe,
   - what tests should be run.
9. For every change, update all documentation, bump versioning, and always create a new PR. Make sure to create tests for the changes and run the tests before creating the PR.
