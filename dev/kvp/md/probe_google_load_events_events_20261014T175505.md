# Google load-event probe

- Mode: events
- Runs: 29, valid: 11, excluded: 18
- Runs with load event later than 3.0 s (would fail in production): 3
- Valid runs where the results DOM never appeared (poll mode): 11
- Valid runs with result containers present at DOMContentLoaded (events mode): 11

| event (ms after navigate) | n | min | p50 | p90 | max |
|---|---|---|---|---|---|
| document_response | 11 | 71 | 106 | 133 | 163 |
| dom_content_loaded | 11 | 836 | 1256 | 1884 | 2008 |
| results_dom | 0 | - | - | - | - |
| load | 11 | 2059 | 2539 | 3059 | 3175 |

Load minus DOMContentLoaded (ms): {'n': 11, 'min': 270, 'p50': 1046, 'p90': 2102, 'max': 2339}

## Runs with a load event later than the production limit

- python dataclass vs namedtuple: {'document_response': 118, 'dom_content_loaded': 957, 'load': 3059, 'go_to_returned': 3121}, requests=69, result containers at end=23
- sourdough starter feeding schedule: {'document_response': 107, 'dom_content_loaded': 836, 'load': 3175, 'go_to_returned': 3189}, requests=97, result containers at end=22
- how to remove rust from cast iron: {'document_response': 108, 'dom_content_loaded': 1193, 'load': 3029, 'go_to_returned': 3032}, requests=106, result containers at end=21

## All runs

| query | document_response | dom_content_loaded | results_dom | load | requests |
|---|---|---|---|---|---|
| python dataclass vs namedtuple | 118 | 957 | - | 3059 | 69 |
| best hiking trails black forest | 75 | 2008 | - | 2278 | 56 |
| sourdough starter feeding schedule | 107 | 836 | - | 3175 | 97 |
| kubernetes pod pending reason | 163 | 1250 | - | 2294 | 72 |
| how to remove rust from cast iron | 108 | 1193 | - | 3029 | 106 |
| european central bank interest rate decision | 133 | 1884 | - | 2862 | 65 |
| typescript generic constraints explained | 106 | 1613 | - | 2659 | 59 |
| marathon training plan 16 weeks | 71 | 1329 | - | 2170 | 74 |
| difference between ssd and nvme | 82 | 1211 | - | 2539 | 78 |
| how to prune apple trees | 76 | 1256 | - | 2428 | 92 |
| postgres index only scan | 79 | 1346 | - | 2059 | 59 |
| history of the hanseatic league | 88 | 494 | - | 1446 | 14 |
| electric car charging cost per kwh | 107 | 700 | - | 2441 | 14 |
| css grid vs flexbox | 90 | 1151 | - | 1857 | 14 |
| how to descale an espresso machine | 102 | 599 | - | 2237 | 14 |
| rust borrow checker lifetimes | 81 | 550 | - | 1700 | 14 |
| safe temperature for cooked chicken | 68 | 512 | - | 1128 | 14 |
| tax deductible home office germany | 72 | 590 | - | 1382 | 14 |
| docker multi stage build size | 74 | 1259 | - | 2170 | 14 |
| causes of the french revolution | 82 | 724 | - | 2681 | 14 |
| how to fix a leaking tap | 115 | 829 | - | 2069 | 14 |
| machine learning cross validation | 182 | 760 | - | 2282 | 14 |
| best time to visit lisbon | 118 | 1352 | - | 2222 | 14 |
| linux file permissions chmod | 106 | 1293 | - | 1959 | 14 |
| how do vaccines train the immune system | 70 | 626 | - | 2139 | 14 |
| photovoltaic payback period germany | 91 | 795 | - | 2148 | 14 |
| git rebase vs merge | 155 | 674 | - | 1951 | 14 |
| how to repot a monstera | 77 | 621 | - | 2027 | 14 |
| tcp congestion control algorithms | 72 | 462 | - | 2194 | 18 |
