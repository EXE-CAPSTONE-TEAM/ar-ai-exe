# SonarCloud Integration

This repository uses SonarCloud through GitHub Actions. The workflow scans code and, after a main-branch or manual scan, creates GitHub Issues for high-risk findings that match the agreed policy.

## Required GitHub Configuration

Add these in GitHub repository or organization settings:

- Secret `SONAR_TOKEN`: SonarCloud token with access to this project.
- Variable `SONAR_PROJECT_KEY`: SonarCloud project key.
- Variable `SONAR_ORGANIZATION`: SonarCloud organization key.
- Optional variable `SONAR_HOST_URL`: defaults to `https://sonarcloud.io`.
- Optional variable `SONAR_FINDING_LABELS`: defaults to `security,bug,sonarqube,priority: high`.
- Optional variable `SONAR_MAX_ISSUES`: defaults to `100`.

Do not commit token values or paste them into chat.

## Workflow Behavior

- Pull requests into `main` run SonarCloud analysis when configuration is available.
- Pushes to `main` and manual `workflow_dispatch` runs also query SonarCloud Web API and create GitHub Issues.
- Issue creation filters to unresolved SonarCloud findings that are code-addressable and match:
  - Type: `VULNERABILITY` or `BUG`
  - Severity: `BLOCKER`, `CRITICAL`, or `HIGH`
- Created issues use labels: `security`, `bug`, `sonarqube`, `priority: high`.
- Each issue body includes a hidden Sonar issue marker so reruns skip duplicates.

## Manual Run

After setting the secret and variables, run:

```bash
gh workflow run sonarcloud.yml --ref main
```

Then review the Actions log and newly created GitHub Issues.

## Notes

SonarCloud must have the project created before the scanner can publish analysis. If `SONAR_PROJECT_KEY` or `SONAR_ORGANIZATION` is missing, the workflow skips pull-request scans with a notice and fails main/manual scans with a clear configuration error.
