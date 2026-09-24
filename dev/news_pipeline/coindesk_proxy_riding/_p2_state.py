# INFRASTRUCTURE

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from p0_pool import PersistentCooldownManager

STALL_TIMEOUT_S   = 3_600.0


@dataclass
class RideRecord:
    proxy_str:        str
    proto:            str
    host_port:        str
    n_ok:             int
    n_regwall:        int
    n_connect_fail:   int
    n_failed:         int
    n_urls_attempted: int
    burned_threshold: bool
    burned_connect:   bool
    ride_s:           float
    positions:        list = field(default_factory=list)


@dataclass
class JobRecord:
    url:           str
    url_hash:      str
    status:        str
    char_count:    int | None
    markdown_len:  int | None
    elapsed_s:     float | None
    error:         str | None
    file:          str | None
    t_start:       datetime
    ride_position: int
    proxy_str:     str


@dataclass
class RiderState:
    url_queue:       asyncio.Queue
    proxy_pool:      list
    cooldown_mgr:    PersistentCooldownManager
    output_dir:      Path
    burn_threshold:  int
    page_timeout_ms: int
    total_urls:      int

    n_ok:            int   = 0
    n_regwall:       int   = 0
    n_failed:        int   = 0
    n_connect_fail:  int   = 0
    in_flight:       int   = 0
    job_records:     list  = field(default_factory=list)
    ride_records:    list  = field(default_factory=list)
    last_progress_mono: float      = field(default_factory=time.monotonic)
    stall_timeout_s:    float      = STALL_TIMEOUT_S
    termination:        str        = "running"
    proxy_cursor:       int        = 0
    proxy_lock:         asyncio.Lock = field(default_factory=asyncio.Lock)
    n_browsers:         int        = 1
    n_slots:            int        = 0
    in_flight_urls:     set        = field(default_factory=set)
    t_job_start:        datetime   = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def all_resolved(self) -> bool:
        return self.url_queue.empty() and self.in_flight == 0
