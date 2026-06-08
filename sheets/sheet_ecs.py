from .common import (
    REGIONS, START_24,
    get_session, cw_metric, safe, max_risk,
    style_header_row, style_data_row, auto_width, title_banner, set_risk_cell,
)


def build_ecs_sheet(wb):
    ws = wb.create_sheet("ECS_Cluster_Report")
    headers = [
        "Cluster", "Service Name", "Launch Type", "Task Definition",
        "Desired", "Running", "Pending",
        "CPU % (Insights)", "Mem % (Insights)",
        "Service Status", "Deployment Rollout",
        "Failure Events (24h)", "OOM / Restart Events",
        "Risk Level", "Recommendation",
    ]
    title_banner(ws, "ECS Cluster & Service Report", len(headers))
    style_header_row(ws, 2, len(headers))
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)

    row    = 3
    rl_col = headers.index("Risk Level") + 1

    for region in REGIONS:
        sess = get_session(region)
        ecs  = sess.client("ecs")
        cw   = sess.client("cloudwatch")

        cluster_arns = safe(lambda: ecs.list_clusters()["clusterArns"], [])

        for cluster_arn in cluster_arns:
            cname = cluster_arn.split("/")[-1]

            svc_arns = []
            try:
                paginator = ecs.get_paginator("list_services")
                for page in paginator.paginate(cluster=cname):
                    svc_arns.extend(page["serviceArns"])
            except Exception:
                pass

            if not svc_arns:
                style_data_row(ws, row, len(headers))
                ws.cell(row, 1, cname)
                ws.cell(row, 2, "(no services)")
                ws.cell(row, 10, "ACTIVE")
                ws.cell(row, rl_col, "Low")
                ws.cell(row, len(headers), "Empty cluster — delete to reduce clutter/cost.")
                set_risk_cell(ws, row, rl_col, "Low")
                row += 1
                continue

            for i in range(0, len(svc_arns), 10):
                batch    = svc_arns[i:i+10]
                services = safe(lambda: ecs.describe_services(cluster=cname, services=batch)["services"], [])

                for svc in services:
                    sname   = svc["serviceName"]
                    desired = svc.get("desiredCount", 0)
                    running = svc.get("runningCount", 0)
                    pending = svc.get("pendingCount", 0)
                    status  = svc.get("status", "UNKNOWN")
                    td_arn  = svc.get("taskDefinition", "")
                    td_disp = td_arn.split("/")[-1] if td_arn else "?"
                    lt      = svc.get("launchType") or "FARGATE"

                    deploys = svc.get("deployments", [])
                    primary = next((d for d in deploys if d["status"] == "PRIMARY"), {})
                    rollout = primary.get("rolloutState", "UNKNOWN")

                    fail_events = 0
                    oom_events  = 0
                    for evt in svc.get("events", []):
                        et  = evt.get("createdAt")
                        msg = evt.get("message", "").lower()
                        if et and et >= START_24:
                            if any(w in msg for w in ["fail", "error", "unable", "stopped", "killed"]):
                                fail_events += 1
                            if "oom" in msg or "killed" in msg:
                                oom_events += 1

                    dims    = [{"Name": "ClusterName", "Value": cname},
                               {"Name": "ServiceName", "Value": sname}]
                    cpu_pct = cw_metric(cw, "ECS/ContainerInsights", "CpuUtilized",    dims)
                    mem_pct = cw_metric(cw, "ECS/ContainerInsights", "MemoryUtilized", dims)

                    risk_level = "Low"
                    rec_parts  = []

                    if status != "ACTIVE":
                        risk_level = "Critical"
                        rec_parts.append(f"Service status is {status}.")

                    if running < desired:
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"{desired - running} task(s) not running ({running}/{desired}). Check stop reasons in CW Logs.")

                    if pending > 0:
                        risk_level = max_risk(risk_level, "Medium")
                        rec_parts.append(f"{pending} pending task(s) — resource contention or image pull issue.")

                    if fail_events > 0:
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"{fail_events} failure event(s) in 24h.")

                    if oom_events > 0:
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"OOM/killed events detected ({oom_events}). Increase memory limit.")

                    if rollout in ("FAILED", "IN_PROGRESS"):
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"Deployment rollout: {rollout}.")

                    if cpu_pct is not None and cpu_pct > 80:
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"Container CPU {cpu_pct}% — scale out tasks.")

                    if mem_pct is not None and mem_pct > 80:
                        risk_level = max_risk(risk_level, "High")
                        rec_parts.append(f"Container memory {mem_pct}% — risk of OOM.")

                    if not rec_parts:
                        rec_parts.append("Service healthy — steady state confirmed.")

                    data = [
                        cname, sname, lt, td_disp,
                        desired, running, pending,
                        cpu_pct if cpu_pct is not None else "N/A (no Insights)",
                        mem_pct if mem_pct is not None else "N/A (no Insights)",
                        status, rollout,
                        fail_events,
                        oom_events if oom_events > 0 else "None",
                        risk_level, " | ".join(rec_parts),
                    ]
                    style_data_row(ws, row, len(headers))
                    for i, val in enumerate(data, 1):
                        ws.cell(row, i, val)
                    set_risk_cell(ws, row, rl_col, risk_level)
                    row += 1

    auto_width(ws)
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 30
