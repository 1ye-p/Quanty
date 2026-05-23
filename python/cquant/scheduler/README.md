# cquant.scheduler

Production scheduling for automated strategy execution.

## Overview

`scheduler` manages when and how often quantitative strategies run.  It
provides:

- **`StrategyScheduler`** — registers jobs, tracks status, and determines
  whether a job is due to run
- **`JobRunner`** — drives execution by polling the scheduler for due jobs
- **`HealthChecker`** — monitors system health and job liveness

Job state (last run, next run, run count, errors) is held in-process by
`StrategyScheduler`.  Persistence to an external store should be added at the
application layer if cross-process durability is required.

---

## ScheduleFrequency

| Value | Description |
|---|---|
| `DAILY` | Run once per trading day |
| `WEEKLY` | Run once per week |
| `MONTHLY` | Run once per month |
| `CUSTOM` | User-defined schedule logic |

---

## ScheduleConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `job_id` | `str` | — | Unique job identifier |
| `strategy_id` | `str` | — | Strategy to execute |
| `frequency` | `ScheduleFrequency` | — | How often to run |
| `run_time` | `datetime.time` | `09:30` | Wall-clock time to trigger |
| `days_of_week` | `list[int]` | `[0,1,2,3,4]` | Days to run (0=Mon … 4=Fri) |
| `enabled` | `bool` | `True` | Whether the job is active |
| `metadata` | `dict[str, Any]` | `{}` | Arbitrary extra config |

## JobStatus Fields

| Field | Type | Description |
|---|---|---|
| `job_id` | `str` | Job identifier |
| `strategy_id` | `str` | Associated strategy |
| `last_run` | `datetime \| None` | Timestamp of last execution |
| `next_run` | `datetime \| None` | Scheduled next execution time |
| `status` | `str` | `"idle"`, `"running"`, `"completed"`, or `"failed"` |
| `error` | `str \| None` | Last error message if failed |
| `run_count` | `int` | Total number of completed runs |

---

## Quick Start

```python
from datetime import time
from cquant.scheduler import StrategyScheduler, JobRunner
from cquant.scheduler.scheduler import ScheduleConfig, ScheduleFrequency

# 1. Create scheduler and register a job
scheduler = StrategyScheduler()

config = ScheduleConfig(
    job_id="daily_momentum",
    strategy_id="top10_momentum",
    frequency=ScheduleFrequency.DAILY,
    run_time=time(9, 30),
)

def run_strategy():
    # execute strategy logic here
    pass

scheduler.add_job(config, run_strategy)

# 2. Check and run due jobs
runner = JobRunner(scheduler)
ran_jobs = runner.check_and_run()   # returns list of job_ids that fired
print(ran_jobs)

# 3. Run all enabled jobs immediately (useful for testing)
results = runner.run_all()          # {job_id: bool}
```

---

## Running as a Daemon

For continuous operation, call `check_and_run` on a regular interval:

```python
import time as time_module
from cquant.scheduler import StrategyScheduler, JobRunner

scheduler = StrategyScheduler()
scheduler.add_job(config, callback)

runner = JobRunner(scheduler)
scheduler.start()

try:
    while True:
        runner.check_and_run()
        time_module.sleep(60)   # poll every minute
except KeyboardInterrupt:
    scheduler.stop()
```

To run a single named job on demand:

```python
runner.run_job("daily_momentum")   # returns True on success
```
