# indiantripper.in (Time Turner)

A static copy of the blog, built from plain files. No WordPress, no database.

## What is where
- `content/posts/<year>/` — one file per post. Top lines are the title, date, categories and tags; the rest is the post.
- `content/comments/<year>/` — the old comments for each post. Comments are closed; these are display-only.
- `content/site.json` — site title, menu, home page and About text.
- `theme/` — the look (stylesheet and script from the Time Turner theme).
- `static/` — optional. Anything placed here is copied to the site as-is, e.g. `static/images/goa.jpg` appears at `/images/goa.jpg`.
- `docs/` — the built site that GitHub Pages serves. Never edit it by hand; it is rebuilt each time.
- `reports/` — import summary, a list of every image address in old posts, and the list of post addresses.

## Build
    python3 build.py                 # production build for https://indiantripper.in
    python3 build.py --serve         # preview on this Mac at http://localhost:8000
    python3 build.py --preview /REPO # build for https://USER.github.io/REPO/ (hidden from search engines)

## Add a post
Create `content/posts/2026/2026-12-01-my-new-post.html`:

    ---
    title: My new post
    date: 2026-12-01 09:00:00
    categories: travel
    tags: goa, beaches
    ---

    First paragraph.

    Second paragraph. A blank line starts a new paragraph. HTML is allowed.

The address becomes `/2026/12/01/my-new-post/`. A Hindi file name gives a Hindi address.
Category names to use are the `slug` values in `content/categories.json`.
Then build, check the preview, commit and push.

## Keep out of this folder
This repository is public. Drafts, password-protected posts and the backups live outside it
(`../private` and `../backup`). Commenter email and IP addresses were never imported.
