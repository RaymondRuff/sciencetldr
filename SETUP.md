# Setup Checklist

One-time tasks to get the pipeline running. Allow ~30–45 minutes total.

---

## 1. GitHub repo configuration (~5 min)

In your `RaymondRuff/sciencetldr` repo:

- **Settings → Pages**
  - Source: **Deploy from a branch**
  - Branch: `main`, folder `/` (root)
- **Settings → Actions → General**
  - Workflow permissions: **Read and write permissions**
  - ✅ Allow GitHub Actions to create and approve pull requests
- **Settings → Code security → Secret scanning**
  - ✅ Enable "Secret scanning alerts"
  - ✅ Enable "Push protection"

---

## 2. Generate credentials (~10 min)

### Anthropic API key
1. Go to https://console.anthropic.com/settings/keys → "Create Key"
2. Name it `sciencetldr-actions`
3. Copy the key

### Gmail app password (for `sciencetldrpod@gmail.com`)
1. Sign in to that account at https://myaccount.google.com
2. **Security → 2-Step Verification** → enable if not already on
3. https://myaccount.google.com/apppasswords → create one named "ScienceTLDR Actions"
4. Copy the 16-character password (spaces don't matter)

### NCBI API key (optional but free)
1. Sign in at https://www.ncbi.nlm.nih.gov/account/
2. **Account Settings → API Key Management** → Create new key
3. Copy. Without this, PubMed limits you to 3 req/sec; with it, 10 req/sec.

### GitHub Personal Access Token (for opening Issues from workflows)
The default `GITHUB_TOKEN` works for most things, but using a fine-grained PAT
gives cleaner attribution.
1. https://github.com/settings/personal-access-tokens/new
2. Repository access: select **only** `RaymondRuff/sciencetldr`
3. Permissions:
   - Issues → **Read and write**
   - Contents → **Read and write**
   - Metadata → **Read** (auto-selected)
4. Expiration: 90 days (rotate quarterly) or longer if you prefer
5. Generate, copy

---

## 3. Add secrets to the repo (~3 min)

**Settings → Secrets and variables → Actions → New repository secret**, add:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from step 2 |
| `GMAIL_APP_PASSWORD` | from step 2 (no spaces) |
| `DIGEST_RECIPIENTS` | comma-separated coworker emails, e.g. `alice@lab.edu,bob@lab.edu` |
| `NCBI_API_KEY` | from step 2 (optional but recommended) |
| `GH_PAT` | from step 2 (optional; falls back to `GITHUB_TOKEN`) |

---

## 4. Local prep — install uv (~2 min)

On your personal machine (not your work computer):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

Then in this repo:

```bash
uv sync
```

This installs all Python dependencies into a local `.venv/`.

---

## 5. Run the back-catalog migration (~1 hour, mostly download time)

```bash
uv run python scripts/migrate_from_rss_com.py
uv run python scripts/feed_builder.py
```

The migration script will:
- Download all 59 episode MP3s into `episodes/` (~600 MB total)
- Write per-episode JSON sidecars with **GUIDs preserved byte-for-byte** so subscribers don't re-download
- Capture channel metadata (cover, owner, category, podcast:guid) into `channel.json`
- Save the cover image to `cover.jpg`

Then `feed_builder.py` produces `feed.xml`.

### Validate before pushing
1. Open `feed.xml` in https://castfeedvalidator.com/ and https://podba.se/validate/ — both should pass with zero errors
2. Sanity-check episode count: `ls episodes/*.mp3 | wc -l` should output a number close to 59 (you mentioned 57; the rss.com feed currently lists 59 — confirm two weren't lost or hidden somewhere)
3. `git status` — review what's being added before committing

### First push
```bash
git add .
git commit -m "initial: migrate 59 episodes from rss.com"
git push -u origin main
```

GitHub Pages will publish within ~2 minutes at:
**https://raymondruff.github.io/sciencetldr/feed.xml**

### Subscribe to the new feed in a test podcast app
[Pocket Casts](https://pocketcasts.com/) lets you subscribe by URL. Paste the feed URL, confirm all episodes appear with cover art and correct dates.

---

## 6. Test the publish pipeline (~10 min)

The publish workflow accepts any of `.mp3 / .m4a / .mp4a / .wav` and resolves
metadata in this order:

1. **JSON sidecar** with the same basename (one-off flow)
2. **Oldest open Issue** with the `podcast-pending` label (digest flow)
3. **Filename fallback** — derive title from the filename; look up DOI via PubMed

### Test the one-off path with a sidecar

1. Pick any short audio file (rename to `inbox/test-episode.m4a`)
2. Create `inbox/test-episode.json` with:
   ```json
   {
     "title": "Test paper for pipeline verification",
     "doi": "10.0000/test",
     "source": "manual-test"
   }
   ```
3. Commit and push both files in one commit. Git web UI caps uploads at 25 MB;
   for larger files use the `git` CLI or GitHub Desktop.
4. Watch the **Actions** tab — `publish` runs and within ~2 min:
   - The audio is transcoded+normalized into `episodes/NNN-test-paper-....mp3`
   - `feed.xml` updates
   - The audio and sidecar are removed from `inbox/`
5. Once verified, revert the test commit:
   ```bash
   git pull
   git revert HEAD -m 1
   git push
   ```

---

## 7. Set up the Claude Code routine (~10 min)

The weekly digest is produced by a **Claude Code routine** (configured at
claude.ai), not by a GitHub Actions job. The routine commits
`digest/YYYY-MM-DD.md` to `main`; that push fires two GitHub workflows:

- **email-digest** — emails the new file to `DIGEST_RECIPIENTS`
- **monday-podcast** — picks the top-DICE paper and opens a podcast Issue

### Create the routine

1. At claude.ai, open **Routines → New routine**
2. **Name:** `Science TLDR weekly digest`
3. **Repo:** link `RaymondRuff/sciencetldr`, allow unrestricted branch pushes
4. **Model:** Opus 4.7
5. **Trigger:** Schedule → Mondays 06:00 ET (cron `0 11 * * 1`)
6. **Connectors:** PubMed and bioRxiv at minimum; the GitHub workflow handles email
7. **Prompt:**
   ```
   Read prompts/digest.md from this repo and follow it to produce this week's
   literature digest. When done, commit the final markdown to
   digest/YYYY-MM-DD.md on main (using today's UTC date).
   ```

### Test it once

1. From the routine page, click "Run now"
2. Wait ~10–15 min
3. Confirm:
   - A new file appeared in `digest/`
   - `email-digest` ran and `DIGEST_RECIPIENTS` received the email
   - `monday-podcast` ran and opened a new Issue

---

## 8. Cutover from rss.com (do this AFTER 2–4 new episodes prove the new feed is healthy)

Run the new feed in parallel for at least one week. Then:

1. Log into https://rss.com → Science TLDR → Settings
2. Look for "Migrate to a new host" or similar (rss.com has a UI field for `<itunes:new-feed-url>`)
3. Paste: `https://raymondruff.github.io/sciencetldr/feed.xml`
4. Save. The rss.com feed will keep serving but include the redirect tag.
5. **Spotify for Podcasters** → Settings → Update RSS feed → paste new URL
6. **Apple Podcasts Connect** → Show settings → New feed URL → paste new URL

**Do not delete the rss.com listing.** Leave it live indefinitely with the redirect tag. Some podcast apps refresh feed indexes only every several months.

Monitor for 30 days — check that the new feed's listener count grows and that no support emails arrive about missing episodes.

---

## Operational notes

- **Cost:** ~$5–10/month total Anthropic API spend. GitHub Pages and Actions are free for public repos within their generous limits.
- **PAT rotation:** rotate `GH_PAT` and `ANTHROPIC_API_KEY` every 90 days. Add a calendar reminder.
- **If the digest runs over Pro plan budget:** tune the routine's model or effort settings at claude.ai. The routine bills against the Pro plan, not the API.
- **If PubMed trending breaks:** the friday workflow will fail loudly with "Only parsed N trending entries". Update the CSS selector in [scripts/select_friday_paper.py](scripts/select_friday_paper.py).
- **Manual override:** any workflow can be triggered on demand via the Actions tab "Run workflow" button.
