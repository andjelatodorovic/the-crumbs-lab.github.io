# CRUMBS website

Jekyll site for the CRUMBS group at Imperial College London.

## Preview locally
    bundle install
    bundle exec jekyll serve --livereload
Then open http://localhost:4000

## Editing
- People: one file per person in `_members/` (photo in `images/people/`, optional `cv:` field)
- News: add an entry at the top of `_data/news.yml`; the home page shows the 4 most recent automatically
- Projects: one file per project in `_projects/`
- Vacancies, Contact, Research: `vacancies.md`, `contact.md`, `research.html`
- Group photo: set `group_photo` in `_config.yml`
- Logo: `images/logo/logo.png` (wordmark, transparent), `images/logo/square.png` and `favicon.png` (icon); `logo-original.jpg` is the source file
