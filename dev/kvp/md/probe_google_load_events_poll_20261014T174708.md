# Google load-event probe

- Runs: 28, valid: 28, excluded: 0
- Runs with load event later than 3.0 s (would fail in production): 14
- Valid runs where the results DOM never appeared: 0

| event (ms after navigate) | n | min | p50 | p90 | max |
|---|---|---|---|---|---|
| document_response | 28 | 68 | 97 | 185 | 1978 |
| dom_content_loaded | 28 | 904 | 1328 | 2115 | 3107 |
| results_dom | 28 | 591 | 1013 | 1450 | 3102 |
| load | 28 | 1565 | 3046 | 4067 | 4209 |

Load minus DOMContentLoaded (ms): {'n': 28, 'min': 356, 'p50': 1717, 'p90': 2402, 'max': 3040}

## Runs with a load event later than the production limit

- python dataclass vs namedtuple: {'document_response': 1978, 'results_dom': 3102, 'dom_content_loaded': 3107, 'load': 4085, 'go_to_returned': 4086}, requests=40, result containers at end=24
- how to remove rust from cast iron: {'document_response': 185, 'results_dom': 1132, 'dom_content_loaded': 2115, 'load': 3890, 'go_to_returned': 3891}, requests=101, result containers at end=21
- typescript generic constraints explained: {'document_response': 125, 'results_dom': 1358, 'dom_content_loaded': 1370, 'load': 3705, 'go_to_returned': 3707}, requests=69, result containers at end=21
- marathon training plan 16 weeks: {'document_response': 136, 'results_dom': 1004, 'dom_content_loaded': 2219, 'load': 3862, 'go_to_returned': 3890}, requests=59, result containers at end=23
- difference between ssd and nvme: {'document_response': 182, 'results_dom': 922, 'dom_content_loaded': 1308, 'load': 3643, 'go_to_returned': 3645}, requests=110, result containers at end=23
- how to prune apple trees: {'document_response': 79, 'results_dom': 1216, 'dom_content_loaded': 1234, 'load': 3636, 'go_to_returned': 3639}, requests=101, result containers at end=21
- history of the hanseatic league: {'document_response': 100, 'results_dom': 775, 'dom_content_loaded': 1186, 'load': 3969, 'go_to_returned': 3971}, requests=102, result containers at end=22
- electric car charging cost per kwh: {'document_response': 145, 'results_dom': 1022, 'dom_content_loaded': 1169, 'load': 4209, 'go_to_returned': 4285}, requests=100, result containers at end=22
- how to descale an espresso machine: {'document_response': 96, 'results_dom': 828, 'dom_content_loaded': 1109, 'load': 3221, 'go_to_returned': 3223}, requests=78, result containers at end=22
- safe temperature for cooked chicken: {'document_response': 140, 'results_dom': 973, 'dom_content_loaded': 1459, 'load': 3683, 'go_to_returned': 3688}, requests=70, result containers at end=22
- causes of the french revolution: {'document_response': 79, 'results_dom': 939, 'dom_content_loaded': 1942, 'load': 4067, 'go_to_returned': 4068}, requests=121, result containers at end=22
- how to fix a leaking tap: {'document_response': 71, 'results_dom': 711, 'dom_content_loaded': 1439, 'load': 3152, 'go_to_returned': 3153}, requests=96, result containers at end=21
- linux file permissions chmod: {'document_response': 98, 'results_dom': 1398, 'dom_content_loaded': 1828, 'load': 3218, 'go_to_returned': 3223}, requests=58, result containers at end=24
- how to repot a monstera: {'document_response': 80, 'results_dom': 1450, 'dom_content_loaded': 1456, 'load': 3252, 'go_to_returned': 3253}, requests=93, result containers at end=21

## All runs

| query | document_response | dom_content_loaded | results_dom | load | requests |
|---|---|---|---|---|---|
| python dataclass vs namedtuple | 1978 | 3107 | 3102 | 4085 | 40 |
| best hiking trails black forest | 190 | 1942 | 1604 | 2304 | 58 |
| sourdough starter feeding schedule | 112 | 1057 | 686 | 2293 | 57 |
| kubernetes pod pending reason | 68 | 1179 | 591 | 2941 | 64 |
| how to remove rust from cast iron | 185 | 2115 | 1132 | 3890 | 101 |
| typescript generic constraints explained | 125 | 1370 | 1358 | 3705 | 69 |
| marathon training plan 16 weeks | 136 | 2219 | 1004 | 3862 | 59 |
| difference between ssd and nvme | 182 | 1308 | 922 | 3643 | 110 |
| how to prune apple trees | 79 | 1234 | 1216 | 3636 | 101 |
| postgres index only scan | 68 | 1213 | 1208 | 2753 | 57 |
| history of the hanseatic league | 100 | 1186 | 775 | 3969 | 102 |
| electric car charging cost per kwh | 145 | 1169 | 1022 | 4209 | 100 |
| css grid vs flexbox | 154 | 1389 | 1379 | 1857 | 69 |
| how to descale an espresso machine | 96 | 1109 | 828 | 3221 | 78 |
| rust borrow checker lifetimes | 83 | 1005 | 685 | 1565 | 55 |
| safe temperature for cooked chicken | 140 | 1459 | 973 | 3683 | 70 |
| tax deductible home office germany | 84 | 1262 | 1261 | 2701 | 69 |
| docker multi stage build size | 109 | 1419 | 703 | 1909 | 66 |
| causes of the french revolution | 79 | 1942 | 939 | 4067 | 121 |
| how to fix a leaking tap | 71 | 1439 | 711 | 3152 | 96 |
| machine learning cross validation | 83 | 904 | 745 | 2625 | 74 |
| best time to visit lisbon | 150 | 1417 | 1403 | 1773 | 65 |
| linux file permissions chmod | 98 | 1828 | 1398 | 3218 | 58 |
| how do vaccines train the immune system | 83 | 1024 | 975 | 2818 | 73 |
| photovoltaic payback period germany | 79 | 1348 | 1336 | 2259 | 54 |
| git rebase vs merge | 79 | 1277 | 1271 | 1678 | 62 |
| how to repot a monstera | 80 | 1456 | 1450 | 3252 | 93 |
| tcp congestion control algorithms | 71 | 932 | 764 | 2871 | 72 |
