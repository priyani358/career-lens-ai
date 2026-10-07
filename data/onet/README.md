# O*NET 31.0 data

`careers_31_0.json` contains CareerLens' adapted occupation catalog generated from the official O*NET 31.0 CSV database.

- Original source: [O*NET 31.0 Database](https://www.onetcenter.org/database.html), U.S. Department of Labor, Employment and Training Administration.
- License: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
- Attribution: CareerLens includes modified content from the O*NET 31.0 Database. O*NET is a registered trademark of the U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). CareerLens is not affiliated with or endorsed by USDOL/ETA.
- Modifications: O*NET essential and transferable skill importance ratings (scale 1–5) are mapped to CareerLens' three-level skill-gap scale; only core task statements and hot/in-demand software examples are retained; other source tables are not included. CareerLens does not infer projects or certifications from the dataset.

To regenerate the adapted JSON from a fresh official CSV archive, download the CSV version from the O*NET database page and run from `backend/`:

```sh
python -m app.onet_import /path/to/db_31_0_csv.zip
```

The importer writes `data/onet/careers_31_0.json` by default. O*NET releases are updated periodically; use the matching importer version and review the mapped fields when moving to a newer release.
