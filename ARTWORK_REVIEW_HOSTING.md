# Standalone Artwork Review Manager

This is a standalone development tool deployed on GitHub Pages from the gh-pages branch. It is not inside BibleQuest's application. The default main branch of Karimen_Reviewer (ALAM) is not modified.

## Zero-cost policy
The site is a static HTML/JavaScript application, using GitHub Pages, the public GitHub API, and GitHub Issues. It requires no paid hosting, Replit, AI API, separate paid database or duplicated binary asset storage. Avoid metered add-ons or surprise overage spending.

## Real image discovery
The public BibleQuest repository is the artwork source of truth. The review tool reads image file paths from its v7/development Git tree and active artwork PRs. Source bytes are never copied. New candidates appear on the next hourly inventory check (or a manual refresh), subject to GitHub API limits.

## Cross-device decision storage
Approve, Reject and Redo generate an owner-authored GitHub issue with a source commit and selected candidate. Reviewers must be signed into GitHub and click Submit new issue to complete each save. On reopening the page, issue records are loaded for the latest status. There is no unverified one-tap persistence claim.

## Scripture, dimensions, rights and integrity
Show authoritative source-side metadata when present, distinguish claims from independently verified real image dimensions, and never mark Scripture as verified without trusted source/context evidence. SVG-only sources are blocked. Visual approval does not waive production release gates.

## Cleanup safety
Reject currently stores a centrally visible cleanup request. Binary deletion is intentionally not automatic until a narrowly authorized GitHub workflow can validate exact hashes, file and revision ownership, sidecars, dependency graph and production usage. Do not erase shared or published artwork or canonical devotional/Scripture content. Git history remains after path deletion.

## Maintenance
The GitHub Pages deployment workflow is on this gh-pages branch at .github/workflows/artwork-review-pages.yml. Do not resume Replit deployments for this tool or import this utility into BibleQuest routes.