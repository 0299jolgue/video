# Rank Clip Studio

An editor for assembling ranked-result clips from your own screenshots, icons, and ending videos. Run `python main.py`; the server listens on **port 80** by default.

## Setup

```sh
pip install -r requirements.txt
python main.py
```

For Docker: `docker build -t rank-video .` followed by `docker run --rm -p 80:80 rank-video`. Set `PORT` only for local development. The hosting entry point is `main.py` and its default port is 80, not 8080. FFmpeg renders H.264 MP4; `imageio-ffmpeg` supplies a binary if the system has none.

Sign in with the temporary account **admin / admin123**. Set `ADMIN_USER`, `ADMIN_PASSWORD`, and `SESSION_SECRET` as environment variables to change it and retain sessions across restarts.

## Editing

- Choose 1–12 scenes (five by default). Each has a final Rank Score, points earned, still image, optional rank icons, and duration. Scores jump at scene boundaries; every still gets a gradual zoom in the preview and MP4.
- Upload a different screenshot per scene or replace the common template. The supplied base screenshot keeps its original Brawlers; separate Brawler/skin replacement remains future work.
- Upload transparent rank icons. Icon files with rank names (Bronze, Silver, Gold, Diamond, Mythic, Legendary, Masters, Pro) automatically match the rank derived from each scene's score; individual selectors can override that. Fine-tune pixel coordinates under “Fine-tune positions.” Icons are not bundled.
- “Generate 5 scores” is an editable starting example. The +100 sample is **not** an official average. Supercell says gains depend on opponent Rank Score and Rank Boost. Review each score and earned amount against your real results.
- Upload your own ending clip (MP4/WebM, up to 60 seconds) and optional background music. The server joins the complete ending after the zoom shots, preserves its audio, and mixes it with optional music. Alternatively use a recreated Masters/Pro end card or no ending. Switching browser tabs does not cancel server rendering.
- Save/open JSON projects with scene images, icons, template, and layout. Re-upload music and ending video after opening a project. Export a still PNG or an MP4 at 720p/1080p, portrait or landscape.

The score bands follow Supercell's [Ranked support page](https://support.supercell.com/brawl-stars/en/articles/about-ranked-3.html): Bronze 0, Silver 750, Gold 1500, Diamond 3000, Mythic 4500, Legendary 6000, Masters 8500, Pro 11250. The support page has inconsistent boundary wording near Gold and Masters; these are the stated starting thresholds. The [Ranked 2025 update](https://supercell.com/en/games/brawlstars/blog/release-notes/ranked-rework-2025/) covers the newer Pro rank and variable point gains. The editor uses major ranks rather than minor divisions.

Files: `main.py` handles login and video rendering, `templates/` contains both HTML pages, `static/` contains the editor and bundled base artwork, and `tests/browser.cjs` exercises the app in Chromium. No rank icons, official animations, or external data service are included.

Run the browser check with Playwright, Chromium, FFmpeg, and ffprobe installed: `TEST_PORT=18080 CHROME_PATH=/path/to/chromium node tests/browser.cjs`. Port 18080 is only for testing; the app defaults to 80.
