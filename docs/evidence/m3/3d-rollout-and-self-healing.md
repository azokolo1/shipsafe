# M3D: rolling deploy and task loss under continuous traffic (2026-10-22)

Stack: `infra/platform` after the M3D PR (#16): `GET /` landing route, and the ALB ordered after the internet gateway. One session: apply on the old image, roll out the new image, stop a task, destroy.

| Image | Tag | Digest |
|---|---|---|
| Old | `98f94bb` | `sha256:61db8ec7f12b8a56a7377c80d96f34cfcadc01857d0a3e3d16709efaf1558b79` |
| New | `d5eebf7` | `sha256:d9c9339429b432de0707101e0fc4a52e4399cdfda02507fe3c3c0135a256f5f3` |

## Method

A client loop requested `GET /version` about twice a second for the whole test, logging time, response body (which includes the version) and status code, with a 3-second timeout. Raw log: [`3d-traffic.log`](3d-traffic.log). The loop ran on one laptop: this tests availability during change, not capacity (load testing is M8).

## Results

### Traffic

| Measure | Result |
|---|---|
| Requests | 890, from 19:58:07.606 to 20:06:15.079 |
| Status codes | 890 × `200`; no timeouts, no 5xx |
| Largest gap between consecutive requests | 0.79 s |

### Rolling deploy, `98f94bb` to `d5eebf7`

Plan: `1 to add, 1 to change, 1 to destroy` (task definition replaced with the new digest; service updated in place; nothing else changed).

| Time | Event |
|---|---|
| 20:01:34 | `terraform apply` starts |
| 20:02:13.244 | first response from `d5eebf7` |
| 20:02:47.090 | ECS deregisters the two old targets, draining starts |
| 20:02:48.880 | last response from `98f94bb` |
| 20:03:49 | deployment completed, service steady; apply took 2m07s |

Both versions served traffic for 35.6 s (32 old and 34 new responses in that window). Every request succeeded.

### Task loss

| Time | Event |
|---|---|
| 20:04:46.200 | `aws ecs stop-task` on one of two tasks |
| 20:05:20.266 | target deregistered, draining starts |
| 20:05:21.185 | replacement task started |
| 20:05:49.712 | replacement registered in the target group |
| — | `aws ecs wait services-stable` returned after 1m12.5s |

118 requests were sent between the stop and the replacement registering; all 118 returned `200`.

### Apply and destroy

| Step | Result |
|---|---|
| Apply on an empty stack | 37 resources, 3m39s (M3C: 4m02s) |
| Destroy | 37 resources. Internet gateway **3 s** (M3C: 2m55s) after the ALB→IGW dependency fix. The total of 7m06s includes time waiting at the confirmation prompt, which was not recorded separately, so it is not a measure of destroy speed. The runbook now times a saved destroy plan instead. |
| After destroy | no VPC, NAT gateway, Elastic IP, load balancer, active cluster or log group left |
| Billing | the stack ran from about 19:34 to about 20:45, so the ALB and NAT gateway most likely billed two started hours (about $0.26 at the ADR-0004 rates) |

## Caveats

1. **Clock jitter.** The log contains 16 points where the timestamp steps backwards by up to 0.96 s, roughly every 28 s: the WSL2 clock being corrected against the Windows host. Line order is reliable; individual timestamps are accurate to about one second. No conclusion here depends on sub-second precision.
2. **One summary command was wrong** during the session (`grep "$TAG_NEW"` ran in a terminal where the variable was unset, so it matched every line). The transition times above come from analysing the full log.
3. **Single client, low rate.** About 2 requests per second from one client. Zero failures at this rate does not prove zero failures under load.
4. **Deregistration lag.** The stopped task's target was deregistered 34 s after the `stop-task` call (13 s in M3C). No request failed during that window in this test; the lag is recorded as observed, not explained.
