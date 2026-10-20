# CRUMBS website

This repository contains the website of the CRUMBS group, built with Jekyll and hosted on GitHub Pages. Any change pushed to `main` goes live within a few minutes.

## Previewing changes locally

Install the dependencies once:

```bash
bundle install
```

Then run the site:

```bash
bundle exec jekyll serve --livereload
```

and open http://localhost:4000. The page reloads automatically when you save a file (restart the server after editing `_config.yml`).

## Publications

The publications list on the Research page is generated automatically. **Do not edit `_data/publications.yml` by hand**, because it is overwritten on every update.

### Where the papers come from

- **Francesco's CV** (`_pubsrc/cv/*.bib`). Francesco updates these by running `make publish` in his CV folder.
- **DBLP**, which adds papers not yet in the CV (typically new arXiv pre-prints) and DOI/arXiv links.
- **`_data/paper_links.yml`**, our hand-written file for code links and corrections.

Only papers co-authored by Francesco are listed. Names of current and former group members are shown in bold automatically, based on the names in `_members/`.

The list updates every Monday, after every `make publish`, and whenever `_data/paper_links.yml` or a member page changes. To update it immediately, go to the **Actions** tab, select **Update publications** and click **Run workflow**.

### Adding a code link (or another fix)

1. Open `_data/publications.yml` and search for your paper's title.
2. Copy its `id` (the first line of the entry).
3. Add an entry to `_data/paper_links.yml` using that id:

```yaml
   my-paper-id-copied-from-publications-yml:
     code: https://github.com/the-crumbs-lab/my-repo
```

4. Commit and push. The list updates within a few minutes.

Besides `code`, you can use these options in the same way:

| Option | What it does |
|---|---|
| `pdf: https://...` | Use this PDF instead of the one found automatically |
| `tag: Workshop` | Change the tag shown before the paper |
| `venue: Proc. of XYZ` | Change the venue text |
| `hide: true` | Remove the paper from the list |

### When a pre-print gets published

Nothing to do. When the published version appears in the CV or on DBLP, it replaces the pre-print automatically and keeps the arXiv PDF and any code link.

The one exception: if the title changed substantially, both versions will appear. In that case, hide the pre-print by adding `hide: true` under its id in `_data/paper_links.yml`.

### Running the generator locally

```bash
pip install bibtexparser==1.4.1 pylatexenc pyyaml
python _scripts/build_publications.py
```

## Member pages

Each member has a page generated from a file in `_members/`, named after the person, e.g. `_members/francesco-leofante.md`. The file name becomes the page address (`/members/francesco-leofante/`).

### Updating your page

1. Open your file in `_members/`.
2. Edit the details between the two `---` lines at the top, and your bio below them.
3. To change your photo, add the image to `images/people/` and update the photo path in your file.
4. Preview locally (see above), then commit and push.

### Adding a new member

Copy an existing member's file, rename it to `firstname-lastname.md`, and replace the details. Use the same spelling of the name as on your papers so it is shown in bold in the publications list.

### When someone leaves the group

Don't delete their file. Set their group to `alumni` instead, so their page stays online and their name stays bold in the publications list.