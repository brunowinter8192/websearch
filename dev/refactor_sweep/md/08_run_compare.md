# 08_run_compare report

runs: 48
identical: 47
different: 1

## Runs

- SAME `dev/agentic_discovery/clean_web_Playwright.py` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_Playwright.py --help` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_anthropic.py` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_anthropic.py --help` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_cookieyes.py` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_cookieyes.py --help` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_onetrust.py` exit=1/1 written=0/0
- SAME `dev/agentic_discovery/clean_web_onetrust.py --help` exit=1/1 written=0/0
- SAME `dev/agentic_discovery/clean_web_rag_docs.py` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_rag_docs.py --help` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_searxng.py` exit=1/1 written=0/0
- SAME `dev/agentic_discovery/clean_web_searxng.py --help` exit=1/1 written=0/0
- SAME `dev/agentic_discovery/clean_web_tor.py` exit=0/0 written=0/0
- SAME `dev/agentic_discovery/clean_web_tor.py --help` exit=0/0 written=0/0
- SAME `dev/lane_choice/04_lane_metrics.py` exit=1/1 written=0/0
- SAME `dev/lane_choice/04_lane_metrics.py --help` exit=1/1 written=0/0
- SAME `dev/logging/01_audit.py` exit=0/0 written=1/1
- SAME `dev/logging/01_audit.py --help` exit=0/0 written=1/1
- SAME `dev/news_pipeline/03_coindesk_cleanup.py` exit=0/0 written=0/0
- DIFF `dev/news_pipeline/03_coindesk_cleanup.py --help` exit=0/0 written=0/0
- SAME `dev/news_pipeline/04_dedup.py` exit=1/1 written=0/0
- SAME `dev/news_pipeline/04_dedup.py --help` exit=0/0 written=0/0
- SAME `dev/scrape_pipeline/03_cleanup/clean.py` exit=0/0 written=19/19
- SAME `dev/scrape_pipeline/03_cleanup/clean.py --help` exit=0/0 written=0/0
- SAME `dev/scrape_pipeline/04_overview_sweep/analyze.py` exit=0/0 written=1/1
- SAME `dev/scrape_pipeline/04_overview_sweep/analyze.py --help` exit=0/0 written=0/0
- SAME `dev/scrape_pipeline/browser_eval/02_regression.py` exit=0/0 written=0/0
- SAME `dev/scrape_pipeline/browser_eval/02_regression.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/ranking_eval/clean_pool.py` exit=0/0 written=17/17
- SAME `dev/search_pipeline/ranking_eval/clean_pool.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/ranking_eval/pool_diff_v2_v3.py` exit=0/0 written=1/1
- SAME `dev/search_pipeline/ranking_eval/pool_diff_v2_v3.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/ranking_eval/stage4_aggregate.py` exit=2/2 written=0/0
- SAME `dev/search_pipeline/ranking_eval/stage4_aggregate.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/ranking_eval/stage4_aggregate_v3.py` exit=2/2 written=0/0
- SAME `dev/search_pipeline/ranking_eval/stage4_aggregate_v3.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/ranking_eval/value_eval_aggregate.py` exit=2/2 written=0/0
- SAME `dev/search_pipeline/ranking_eval/value_eval_aggregate.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/report_analysis/engine_distribution_analysis.py` exit=0/0 written=1/1
- SAME `dev/search_pipeline/report_analysis/engine_distribution_analysis.py --help` exit=0/0 written=1/1
- SAME `dev/search_pipeline/report_analysis/engine_health_audit.py` exit=1/1 written=0/0
- SAME `dev/search_pipeline/report_analysis/engine_health_audit.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/report_analysis/inspect_query_log.py` exit=1/1 written=0/0
- SAME `dev/search_pipeline/report_analysis/inspect_query_log.py --help` exit=0/0 written=0/0
- SAME `dev/search_pipeline/report_analysis/snippet_quality_analysis.py` exit=0/0 written=1/1
- SAME `dev/search_pipeline/report_analysis/snippet_quality_analysis.py --help` exit=0/0 written=1/1
- SAME `dev/search_pipeline/report_analysis/snippet_selection_simulator.py` exit=0/0 written=1/1
- SAME `dev/search_pipeline/report_analysis/snippet_selection_simulator.py --help` exit=0/0 written=1/1

## Differences

### dev/news_pipeline/03_coindesk_cleanup.py --help
```
{
 "base": {
  "exit": 0,
  "out": "usage: 03_coindesk_cleanup.py [-h] [--input INPUT] [--output OUTPUT]\n\nCoinDesk article cleanup \u2014 extract body, strip nav/footer noise, normalize.\n\noptions:\n  -h, --help       show this help message and exit\n  --input INPUT    Input dir of scraped .md files (default: /private/tmp/wsdev\n                   _base.eXOH/inttree2/dev/news_pipeline/02b_data)\n  --output OUTPUT  Output dir for cleaned .md files (default: /private/tmp/wsd\n                   ev_base.eXOH/inttree2/dev/news_pipeline/03_data)\n",
  "err": "",
  "written": []
 },
 "cur": {
  "exit": 0,
  "out": "usage: 03_coindesk_cleanup.py [-h] [--input INPUT] [--output OUTPUT]\n\nCoinDesk article cleanup \u2014 extract body, strip nav/footer noise, normalize.\n\noptions:\n  -h, --help       show this help message and exit\n  --input INPUT    Input dir of scraped .md files (default: /private/tmp/wsdev\n                   _base.eXOH/curtree_q1/dev/news_pipeline/02b_data)\n  --output OUTPUT  Output dir for cleaned .md files (default: /private/tmp/wsd\n                   ev_base.eXOH/curtree_q1/dev/news_pipeline/03_data)\n",
  "err": "",
  "written": []
 }
}
```

