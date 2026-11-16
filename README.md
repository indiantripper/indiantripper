# indiantripper.in (Time Turner)

A static copy of the blog, built from plain files. No WordPress or content database. The browser editor saves back to this repository.

## What is where
- `content/posts/<year>/` — one file per post. Top lines are the title, date, categories and tags; the rest is the post.
- `content/comments/<year>/` — the old comments for each post. Comments are closed; these are display-only.
- `content/site.json` — site title, menu, home page and About text.
- `theme/` — the open notebook stylesheet and reading-preference script.
- `static/` — optional. Anything placed here is copied to the site as-is, e.g. `static/images/goa.jpg` appears at `/images/goa.jpg`.
- `docs/` — the built site that GitHub Pages serves. Never edit it by hand; it is rebuilt each time.
- `reports/` — import summary, a list of every image address in old posts, and the list of post addresses.

## Build
Install the parser once in a local environment:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Use `.venv/bin/python` for the commands below (or activate the environment first).

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

## Images that travel with the blog

Store the web-sized copy of each image in `static/images/<year>/<post-slug>/`.
For this post, the files are `static/images/2026/48-ghante-ka-din/rooftop.jpg`
and `night-reading.jpg`. Refer to them in the post using a site-relative URL:

    <figure>
      <img src="/images/2026/48-ghante-ka-din/rooftop.jpg"
           alt="Describe the image" width="1280" height="853">
      <figcaption>Optional caption</figcaption>
    </figure>

The build copies `static/` into `docs/`. Preview builds add their path prefix to
local image URLs automatically. Uploading a file only to `static/` on GitHub does
not publish it: rebuild and commit `docs/` as well. Do not link images to GitHub
raw-file URLs or temporary upload URLs.

Keep full-resolution originals outside this public repository and publish
compressed JPEG/WebP copies. The two illustrations for “48 घंटे का दिन” are
roughly 300–350 KB each. To move hosts later, carry `content/`, `static/`, the
builder and theme together, then rebuild. Keeping the `/images/` paths preserves
the image links. Original artwork and generation prompts are saved separately
in the task's `48-ghante-ka-din` review folder; only the small website copies
are committed here. The two illustrations are stored with the post’s website assets.

## Share a post

Every individual post has a Share menu next to the reading controls: WhatsApp,
Copy link, Save image, and (on supported secure browsers) native link/image sharing.
The menu never sends anything until the reader chooses a destination.

Social link previews use each post's title, excerpt and local image. Add optional
front-matter fields to choose the image explicitly:

    image: /images/2026/48-ghante-ka-din/rooftop.jpg
    image_alt: A short description of the image

Otherwise, the first local `/images/` picture in the post is used. Posts without
one use `static/images/share/time-turner.jpg`. Old external pictures are not
selected automatically, since many are missing. Open Graph and large-image card
metadata are included in the static HTML. Messaging apps decide how to display
and cache previews; their crawler must be able to access the page and image.
Native Web Share and clipboard APIs require a secure context; the page keeps
WhatsApp, a manual/legacy copy fallback, and Save image available without them.

## Write and publish in the browser

Open https://indiantripper.in/admin/ or the secure editor directly:
https://app.pagescms.org/indiantripper/indiantripper/main/collection/posts

1. Sign in with the `indiantripper` GitHub account.
2. In **Posts**, open an existing post or choose **New entry**.
3. Fill in the title, date and Threads. Write or paste into **Your post**.
4. Use the image tool to upload photos inside the article. **Share cover** picks
   the preview image shown when a link is shared. Uploaded images stay under
   `static/images/`, with public URLs under `/images/`.
5. **Save** publishes immediately. Wait for the **Publish blog** run to finish,
   then reload the blog. No local build or terminal commands are required.

This is a public repository. Saved post text and uploaded images are public,
including old versions in Git history. This setup deliberately has no draft
status. Keep unfinished writing outside this editor until ready to publish.
The editor's rich-text view previews formatting; its Source tab is optional.

GitHub Pages now deploys the artifact produced by
`.github/workflows/publish.yml`, rather than serving the checked-in `docs/`
folder directly. Editor commits trigger the Python build automatically. The
last successful deployment stays live if a later build fails. `docs/` is a
local build output/snapshot; rebuild from `content/`, `static/` and `theme/`
when migrating or testing locally. Do not manually publish a stale `docs/`.

The one-time Pages CMS GitHub App installation must be restricted to
`indiantripper/indiantripper`. No access to `gitagraph.com` or other repositories
is needed. No GitHub token is embedded in the website.

The editor accepts HTML bodies and YAML frontmatter, including list-valued
Threads, quoted titles, multiline summaries and dates. All legacy post bodies,
IDs, addresses and comments are preserved. Existing paths and IDs stay hidden
and read-only in the editor; unknown frontmatter (such as old tags) is preserved.
Filenames are generated only when a post is created, with a timestamp to avoid
collisions for Hindi titles. Renaming files is disabled so title/date edits do
not change a post's address.
