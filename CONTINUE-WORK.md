# Continue working on Time Turner

This file is the handover for a fresh editor or AI chat. Read it with `README.md` and `BACKLOG.md` before editing.

## Where the blog lives

- Website: https://indiantripper.in/
- Complete public source and web-sized images: https://github.com/indiantripper/indiantripper
- Main working copy on Harsh's Mac: `/Users/harshsingh/Documents/indiantripper-migration/site`
- GitHub Pages publishes the built site. Cloudflare manages DNS; Hostinger is the registrar.
- Browser editor: https://indiantripper.in/admin/ (Pages CMS).
- Original migration backups and private material are outside the public repo, in the sibling `backup/` and `private/` directories on this Mac. They do not come with a GitHub clone. Do not upload them to the public repo.
- Earlier visual prototypes and some full-size generated artwork are in `/Users/harshsingh/.codex/visualizations/2026/11/16/01a1e2f7-2b1a-70f0-9e46-a726dca12a76`. Published web images are already in the repo; these review files are not required to build the blog.

## Another ChatGPT/Codex account on this Mac

Open the existing blog folder in the app, then ask the new chat to read this file, `README.md` and `BACKLOG.md`. The files are ordinary files on the Mac; use the folder as the project context. Connect or sign in to GitHub with an account that can write to this repository before publishing. This handover supplies the project context without needing the earlier chat.

## Another Mac or computer

Clone `https://github.com/indiantripper/indiantripper.git`, then open the cloned folder. All public posts, comments, site settings, theme, web images and publishing workflow come with it. A different GitHub account must be invited as a collaborator to publish to the same repo; a different ChatGPT account alone does not grant GitHub access. Keep the existing repo and domain; a fork is not needed for continuing this site.

For writing only, use the browser editor from any device with the authorised GitHub login. Saving publishes immediately after the deployment completes. No drafts workflow is configured.

## Source map and local checks

- `content/posts/`: post text, metadata and category memberships.
- `content/comments/`: historic comments; keep IDs and threads intact.
- `content/categories.json`: English thread labels, ordered by post count at build time.
- `content/start-here.json`: curated Favourites groups.
- `content/share-links.json`: stable short share slugs by post ID. Individual posts can also set `share_slug`.
- `content/share-cards.json`: source copy for the five typographic share cards. Rendered JPEGs live in `static/images/share/cards/`; the optional macOS tool `tools/render-share-cards.swift` regenerates them.
- `static/images/`: portable public images served at `/images/...`.
- `theme/`, `build.py`: layout, behaviour and builder.
- `.pages.yml`: browser editor configuration.
- `.github/workflows/publish.yml`: automatic build and publication on pushes to `main`.
- `docs/`: generated output. Do not edit or commit it for normal updates.

Create a Python virtual environment and install `requirements.txt`, then run:

```
python -m unittest discover -s tests -v
python build.py
```

To preview: `python build.py --serve`. Commit the source changes and push to `main`; check the Publish blog run and the live changed pages. Pull the latest changes before editing, especially if the browser editor has been used. Build failure leaves the last successful deployment live.

## Editorial decisions to preserve

- Title: Time Turner. Subtitle: Stories from my life 🌱. Inspired by Harry Potter; earlier domain magicalharsh.com.
- Compact desktop/mobile header; light/dark appearance and reader text-size controls.
- Navigation uses Favourites, Threads and Through the years. No large introductory hero or Harsh's notebook block.
- Only categories, English names; no tags UI. Stable legacy category slugs remain.
- Preserve original post URLs, post text and all historical comments. Comments stay closed; no empty-comments section.
- Short `/read/.../` links serve the complete article with the original address canonical. Share controls use the short link; old links and archive entries stay intact.
- `share_image` is an optional sharing-only override. Title cards should not become in-article illustrations or thumbnails. `image` and the first local post photo remain normal cover/thumbnail choices.
- The approved प्रेत आत्माएं mosquito-net illustration is in the post and used in sharing. अंतिम ऋण has an approved Kumbhakarna/Vibhishana illustration.
- वक्त now has an illustration of personified Time trapped in a spreadsheet cell, used in the article and sharing. The earlier वक्त title card is retained as an unused fallback asset.
- Do not publish the deferred महाकाली, किताबें और दोस्ती or रात illustration experiments. No realistic invented likeness of Harsh.
- Ignore Kalsubai photo recovery until a new instruction. Other image gaps and link-recovery reports are under `reports/`.
- No messages, email, external accounts or DNS changes are needed for routine blog updates.

## Remaining priorities

See `BACKLOG.md`. The ordered अंतर्द्वंद series page, follow-by-email/WhatsApp, archive resurfacing, image recovery and editorial proofreading remain separate tasks. Do not rewrite historical prose or reopen comments just because external feedback recommends it.
