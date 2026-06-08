from .common import (
    REGIONS, NOW,
    get_session, safe, tag, max_risk,
    style_header_row, style_data_row, auto_width, title_banner, set_risk_cell,
)


def build_ebs_sheet(wb):
    ws = wb.create_sheet("EBS_Volumes_Report")
    headers = [
        "Volume ID", "Name", "Region", "Type", "Size (GB)",
        "State", "Encrypted", "Attached To",
        "IOPS", "Throughput",
        "Last Snapshot", "Snapshot Age (days)",
        "Risk Level", "Recommendation",
    ]
    title_banner(ws, "EBS Volumes & Snapshots", len(headers))
    style_header_row(ws, 2, len(headers))
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)

    row    = 3
    rl_col = headers.index("Risk Level") + 1

    for region in REGIONS:
        sess = get_session(region)
        ec2  = sess.client("ec2")

        vols = safe(lambda: ec2.describe_volumes()["Volumes"], [])

        snap_map = {}
        try:
            account_id = get_session(region).client("sts").get_caller_identity()["Account"]
            for s in ec2.describe_snapshots(OwnerIds=[account_id])["Snapshots"]:
                vid = s.get("VolumeId")
                if vid:
                    prev = snap_map.get(vid)
                    if not prev or s["StartTime"] > prev["StartTime"]:
                        snap_map[vid] = s
        except Exception:
            pass

        for v in vols:
            vid     = v["VolumeId"]
            vname   = tag(v.get("Tags"), "Name")
            vtype   = v.get("VolumeType", "—")
            size_gb = v.get("Size", 0)
            state   = v.get("State", "—")
            encrypt = "Yes" if v.get("Encrypted") else "No"
            iops    = v.get("Iops", "—")
            thru    = v.get("Throughput", "—")
            attached_to = ", ".join(a["InstanceId"] for a in v.get("Attachments", [])) or "NOT ATTACHED"

            snap = snap_map.get(vid)
            if snap:
                snap_date = snap["StartTime"].strftime("%Y-%m-%d")
                snap_age  = (NOW - snap["StartTime"]).days
            else:
                snap_date = "No snapshot"
                snap_age  = 9999

            risk_level = "Low"
            rec_parts  = []

            if encrypt == "No":
                risk_level = max_risk(risk_level, "High")
                rec_parts.append("Unencrypted — create encrypted copy and replace.")

            if attached_to == "NOT ATTACHED":
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append("Volume detached — cost accruing. Delete if not needed.")

            if snap_age == 9999:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append("No snapshots — data loss risk. Create backup immediately.")
            elif snap_age > 7:
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append(f"Last snapshot {snap_age} days ago — schedule more frequent backups.")

            if state not in ("in-use", "available"):
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"Volume state '{state}' — investigate.")

            if not rec_parts:
                rec_parts.append("Volume healthy.")

            data = [
                vid, vname, region, vtype, size_gb,
                state.upper(), encrypt, attached_to,
                iops, thru, snap_date,
                snap_age if snap_age < 9999 else "N/A",
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
