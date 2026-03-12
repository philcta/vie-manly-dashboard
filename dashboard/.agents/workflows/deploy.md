---
description: Build, commit, and deploy the dashboard to Vercel
---

## Deploy Dashboard

// turbo-all

1. Build the project to check for errors:
```bash
npm run build
```
Working directory: `f:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24\dashboard`

2. Stage, commit, and push to trigger Vercel auto-deploy:
```bash
git add -A && git commit -m "<COMMIT_MESSAGE>" && git push origin master
```
Working directory: `f:\1. PROPERTY TRACKS\9. Marketing\Content\2026\Denoux\App24`

3. Verify the push succeeded (check last line for `master -> master`).
