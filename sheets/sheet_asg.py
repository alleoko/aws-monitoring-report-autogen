from .common import (
    REGIONS,
    get_session, safe, max_risk,
    style_header_row, style_data_row, auto_width, title_banner, set_risk_cell,
)


def build_asg_sheet(wb):
    ws = wb.create_sheet("AutoScaling_Report")
    headers = [
        "ASG Name", "Region", "Min", "Max", "Desired",
        "Running (InService)", "Launch Template / Config",
        "Health Check", "Cooldown (s)",
        "Scaling Policies", "Termination Policy",
        "Risk Level", "Recommendation",
    ]
    title_banner(ws, "Auto Scaling Groups Report", len(headers))
    style_header_row(ws, 2, len(headers))
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)

    row    = 3
    rl_col = headers.index("Risk Level") + 1

    for region in REGIONS:
        sess = get_session(region)
        asg  = sess.client("autoscaling")

        groups = safe(lambda: asg.describe_auto_scaling_groups()["AutoScalingGroups"], [])
        for g in groups:
            aname   = g["AutoScalingGroupName"]
            min_s   = g.get("MinSize", 0)
            max_s   = g.get("MaxSize", 0)
            desired = g.get("DesiredCapacity", 0)
            running = sum(1 for i in g.get("Instances", []) if i["LifecycleState"] == "InService")
            lc      = (g.get("LaunchConfigurationName")
                       or (g.get("LaunchTemplate") or {}).get("LaunchTemplateName", "N/A"))
            hc_type  = g.get("HealthCheckType", "—")
            cooldown = g.get("DefaultCooldown", 0)
            policies = safe(lambda: len(asg.describe_policies(AutoScalingGroupName=aname)["ScalingPolicies"]), 0)
            term_pol = ", ".join(g.get("TerminationPolicies", []))

            risk_level = "Low"
            rec_parts  = []

            if min_s == max_s:
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append("Min == Max — static capacity, no auto-scaling.")

            if min_s == 0:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append("Min = 0 — service can scale to zero, causing outage.")

            if running < desired:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"{running}/{desired} InService — check instance health.")

            if policies == 0:
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append("No scaling policies — add CPU/request-based scaling.")

            if cooldown < 60:
                rec_parts.append(f"Cooldown {cooldown}s is short — risk of scale flapping.")

            if not rec_parts:
                rec_parts.append("ASG configured correctly.")

            data = [
                aname, region, min_s, max_s, desired, running,
                lc, hc_type, cooldown, policies, term_pol,
                risk_level, " | ".join(rec_parts),
            ]
            style_data_row(ws, row, len(headers))
            for i, val in enumerate(data, 1):
                ws.cell(row, i, val)
            set_risk_cell(ws, row, rl_col, risk_level)
            row += 1

    if row == 3:
        ws.cell(3, 1, "No Auto Scaling Groups found.")

    auto_width(ws)
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 30
