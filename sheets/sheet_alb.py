from .common import (
    REGIONS,
    get_session, cw_metric, safe, max_risk,
    style_header_row, style_data_row, auto_width, title_banner, set_risk_cell,
)


def build_alb_sheet(wb):
    ws = wb.create_sheet("LoadBalancer_Report")
    headers = [
        "LB Name", "Type", "Region", "Scheme", "State",
        "DNS Name", "Requests (24h)", "4xx Errors", "5xx Errors",
        "Avg Response Time", "Unhealthy Targets",
        "Risk Level", "Recommendation",
    ]
    title_banner(ws, "Load Balancer Health Report", len(headers))
    style_header_row(ws, 2, len(headers))
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)

    row    = 3
    rl_col = headers.index("Risk Level") + 1

    for region in REGIONS:
        sess  = get_session(region)
        elbv2 = sess.client("elbv2")
        cw    = sess.client("cloudwatch")

        lbs = safe(lambda: elbv2.describe_load_balancers()["LoadBalancers"], [])
        for lb in lbs:
            lbname = lb["LoadBalancerName"]
            lbtype = lb.get("Type", "application").upper()
            scheme = lb.get("Scheme", "—")
            state  = lb["State"]["Code"]
            dns    = lb.get("DNSName", "—")
            lb_arn = lb["LoadBalancerArn"]

            dims = [{"Name": "LoadBalancer",
                     "Value": "/".join(lb_arn.split("/")[-3:])}]
            req4xx    = cw_metric(cw, "AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", dims, stat="Sum", period=86400)
            req5xx    = cw_metric(cw, "AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count",    dims, stat="Sum", period=86400)
            req_total = cw_metric(cw, "AWS/ApplicationELB", "RequestCount",              dims, stat="Sum", period=86400)
            resp_time = cw_metric(cw, "AWS/ApplicationELB", "TargetResponseTime",        dims)
            resp_ms   = round(resp_time * 1000, 1) if resp_time is not None else None

            unhealthy = 0
            try:
                for tg in elbv2.describe_target_groups(LoadBalancerArn=lb_arn)["TargetGroups"]:
                    for h in elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])["TargetHealthDescriptions"]:
                        if h["TargetHealth"]["State"] != "healthy":
                            unhealthy += 1
            except Exception:
                pass

            risk_level = "Low"
            rec_parts  = []

            if state != "active":
                risk_level = "Critical"
                rec_parts.append(f"LB state '{state}' — not active.")

            if unhealthy > 0:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"{unhealthy} unhealthy target(s) — check target group health.")

            if req5xx is not None and req5xx > 100:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"{int(req5xx)} 5xx errors (24h) — backend errors, check logs.")
            elif req5xx is not None and req5xx > 10:
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append(f"{int(req5xx)} 5xx errors — monitor.")

            if resp_ms is not None and resp_ms > 2000:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"Avg response {resp_ms}ms — investigate backend performance.")
            elif resp_ms is not None and resp_ms > 1000:
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append(f"Elevated response time {resp_ms}ms.")

            if scheme == "internet-facing":
                rec_parts.append("Internet-facing — verify WAF is attached and access logs are enabled.")

            if not rec_parts:
                rec_parts.append("Load balancer healthy.")

            data = [
                lbname, lbtype, region, scheme, state.upper(), dns,
                int(req_total) if req_total is not None else "N/A",
                int(req4xx)    if req4xx   is not None else "N/A",
                int(req5xx)    if req5xx   is not None else "N/A",
                f"{resp_ms}ms" if resp_ms  is not None else "N/A",
                unhealthy,
                risk_level, " | ".join(rec_parts),
            ]
            style_data_row(ws, row, len(headers))
            for i, val in enumerate(data, 1):
                ws.cell(row, i, val)
            set_risk_cell(ws, row, rl_col, risk_level)
            row += 1

    if row == 3:
        ws.cell(3, 1, "No Load Balancers found.")

    auto_width(ws)
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 30
