# indiantripper.in (Time Turner)

A static copy of the blog, built from plain files. No WordPress, no database.

## What is where
- `content/posts/<year>/` — one file per post. Top lines are the title, date, categories and tags; the rest is the post.
- `content/comments/<year>/` — the old comments for each post. Comments are closed; these are display-only.
- `content/site.json` — site title, menu, home page and About text.
- `theme/` — the open notebook stylesheet and reading-preference script.
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

## Open notebook theme
The brand links home. Threads (`/threads/`) browses categories; Years (`/years/`) browses the dated archive. Each thread and year has its own paginated, directly linkable page. The post-language choice in Reading controls filters stories within the selected thread or year. Thread names always show both Hindi and English.

The moon/sun button changes appearance. The sliders button opens text size and post-language controls. Text size and appearance stay in that reader’s browser. Reading text starts at 21px; the size controls range from 19px to 27px. English category labels are `name_en` in `content/categories.json`.

Only posts with existing comments show a discussion. New comments stay closed. Tags have no links or labels in the theme; old tag archive addresses are retained as unlisted, noindex compatibility pages.

A preview build still uses `/indiantripper/`, `noindex`, and blocking robots.txt. Do not add a CNAME or switch DNS until the domain migration is approved.
