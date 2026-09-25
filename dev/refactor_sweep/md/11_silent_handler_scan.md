# 11_silent_handler_scan report

silent handlers without a trace: 0
silent handlers left as intended: 23

## Findings


## Intended (exception type is the expected control flow)

- dev/_lib/browser_launch.py:67 except asyncio.CancelledError (task cancellation during cleanup)
- dev/brave_return/_brave_probe_launch.py:113 except asyncio.CancelledError (task cancellation during cleanup)
- dev/brave_return/_brave_probe_launch.py:217 except psutil.NoSuchProcess (process exited between listing and access (race))
- dev/brave_return/_brave_probe_launch.py:223 except psutil.NoSuchProcess (process exited between listing and access (race))
- dev/browser_posture/04_headed_chromium_probe.py:147 except psutil.Error (process exited (race))
- dev/browser_posture/04_headed_chromium_probe.py:152 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/04_headed_chromium_probe.py:120 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/05_cdp_headed_probe.py:135 except psutil.Error (process exited (race))
- dev/browser_posture/05_cdp_headed_probe.py:140 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/05_cdp_headed_probe.py:81 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/_cdp_teardown.py:25 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/_cdp_teardown.py:32 except psutil.NoSuchProcess,psutil.AccessDenied (process exited between listing and access (race))
- dev/browser_posture/_chromium_teardown.py:19 except psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess (process exited between listing and access (race))
- dev/browser_posture/_chromium_teardown.py:27 except psutil.NoSuchProcess,psutil.AccessDenied (process exited between listing and access (race))
- dev/mojeek_return/_mojeek_pydoll_probe_launch.py:99 except asyncio.CancelledError (task cancellation during cleanup)
- dev/mojeek_return/_mojeek_pydoll_probe_launch.py:196 except psutil.NoSuchProcess (process exited between listing and access (race))
- dev/mojeek_return/_mojeek_pydoll_probe_launch.py:202 except psutil.NoSuchProcess (process exited between listing and access (race))
- dev/news_pipeline/coindesk_proxy_riding/_p2_watchdog.py:54 except asyncio.QueueEmpty (queue drain loop end)
- dev/news_pipeline/coindesk_proxy_riding/p2_browser_rider.py:238 except asyncio.TimeoutError (expected wait timeout as control flow)
- dev/search_pipeline/24_pydoll_teardown_verify.py:296 except asyncio.TimeoutError (expected wait timeout as control flow)
- dev/search_pipeline/browser_probes/altcha_trigger_probe.py:271 except asyncio.CancelledError (task cancellation during cleanup)
- dev/search_pipeline/browser_probes/altcha_trigger_probe.py:334 except asyncio.TimeoutError (expected wait timeout as control flow)
- dev/tests/test_death_pipe.py:133 except psutil.NoSuchProcess (process exited between listing and access (race))

## Exempt files

- `dev/news_pipeline/theblock/jhao104/patches/helper/validator.py`: verbatim overlay of the vendored upstream helper/validator.py: copied over the upstream clone by jhao104/setup.sh, must stay diffable against upstream, and its decorator registration at definition time (ProxyValidator.addPreValidator) pins the definition order

