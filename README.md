# Tack - A tool to catalogue your read papers

`tack` is a simple cli-based tool, designed to work together with [Obsidian](https://obsidian.md/) to provide an
efficient way to manage your papers.

It automatically grabs paper metadata from the internet and generates you markdown documents.

## Usage:

Install with your favourite package manager `<anything> install tack`. (TODO: actually publish on pypi).

Before you can use `tack`, you need to set it up. For this type `tack migrate`. This will set up the DB and stuff.

Then you can add papers through their DOI: `tack add <doi>`. This will fetch metadata and generate a markdown file like this in `~/papers/10.1145/3620666.3651344.md`:

```md
---
aliases:
- A shared compilation stack for distributed-memory parallelism in stencil DSLs
authors:
- George Bisbas
- Anton Lydike
// ...
conference: ASPLOS '24
url: http://dx.doi.org/10.1145/3620666.3651344
year: 2024
---
# A shared compilation stack for distributed-memory parallelism in stencil DSLs
## Notes

## References
- [[10.5555/3026877.3026899]]
- [[10.1016/j.jpdc.2019.02.007|LFRic: Meeting the challenges of scalability and performance portability in Weather and Climate models]] (S.V. Adams et. al. - 2019)
- [[10.1016/j.softx.2021.100707|GridTools: A framework for portable weather and climate applications]] (Anton Afanasyev et. al. - 2021)
// ...
```

These markdown files are meant to be managed through Obsidian+git.

You have links, backlinks, etc. Adding new papers works just by `tack add <doi>`.

## How it works

Tack has an internal sqlite database to cache API responses and manage your library. You could probably do some cool data analysis with that data later.

If you want to add something but tack tells you you already have it, you can `tack remove <doi>` to remove it from the database. You can then re-add it.

You can list all added papers through: `tack list`.

TODO: write more in-depth

## (Missing) features:

- [ ] Grab references that don't have a DOI attached 
- [ ] We can't reliably grab the abstract
- [ ] We have some trouble with rate limits
- [X] Read notes when regenerating a file
- [ ] We need a tool to deduplicate authors at some point
- [ ] tag management
- [X] markdown -> sqlite reader
- [X] Author list is broken?
- [ ] settings management from cli
- [ ] Have the `tack.db` be located in `$XDG_DATA_DIR` or something
- [ ] Make `tack migrate` interactive or add interactive `tack init`
- [X] Allow manual adding
- [ ] Maybe auto-download papers or something?
- [ ] Fix casing in all-uppercase submissions
- [ ] ORCID API?
- [ ] Datacite API?
- [ ] Web-scraping extension?
  - [ ] `dc.acm.org` can be scraped with `curl` 
  - [ ] `dl.acm.org/doi/pdf/<doi>` can just be `wget`-ed :scream:
- [X] Basic autocomplete
  - [ ] Advanced Autocomplete 

### Data Analysis Tools:

- [ ] Most cited papers that you missed
- [ ] Most read authors
- [ ] Papers from popular authors that you haven't read
- [ ] Popular papers from conferences you follow that you missed
