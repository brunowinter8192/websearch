# 01_layout_scan report

files scanned: 337 (EXEMPT=1, LIB=126, SCRIPT=130, TEST=80)
files with findings: 0
findings total: 0

## Findings by code


## Exempt files

- `dev/news_pipeline/theblock/jhao104/patches/helper/validator.py`: verbatim overlay of the vendored upstream helper/validator.py: copied over the upstream clone by jhao104/setup.sh, must stay diffable against upstream, and its decorator registration at definition time (ProxyValidator.addPreValidator) pins the definition order

## Files

