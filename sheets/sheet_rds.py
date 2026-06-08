from .common import (
    REGIONS, NOW, START_24,
    get_session, cw_metric, safe, max_risk,
    style_header_row, style_data_row, auto_width, title_banner, set_risk_cell,
)


def build_rds_sheet(wb):
    ws = wb.create_sheet("RDS_Health_Report")
    headers = [
        "DB Identifier", "Engine", "Class", "Region", "AZ",
        "Status", "Multi-AZ", "Storage Auto-Scale",
        "CPU Avg %", "Free Storage (GB)", "Connections Avg",
        "Backup Retention (days)", "Latest Restore Point",
        "Encryption", "Publicly Accessible",
        "Events (24h)",
        "Risk Level", "Recommendation",
    ]
    title_banner(ws, "RDS Health Report", len(headers))
    style_header_row(ws, 2, len(headers))
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)

    row    = 3
    rl_col = headers.index("Risk Level") + 1

    for region in REGIONS:
        sess = get_session(region)
        rds  = sess.client("rds")
        cw   = sess.client("cloudwatch")

        instances = safe(lambda: rds.describe_db_instances()["DBInstances"], [])
        clusters  = safe(lambda: rds.describe_db_clusters()["DBClusters"],   [])
        covered   = set()

        for db in instances:
            dbid      = db["DBInstanceIdentifier"]
            engine    = f"{db['Engine']} {db.get('EngineVersion','')}"
            cls       = db["DBInstanceClass"]
            az        = db.get("AvailabilityZone", "—")
            status    = db["DBInstanceStatus"]
            multi_az  = "Yes" if db.get("MultiAZ") else "No"
            auto_stor = "Yes" if db.get("MaxAllocatedStorage") else "No"
            encrypt   = "Yes" if db.get("StorageEncrypted")    else "No"
            pub_acc   = "YES – Exposed" if db.get("PubliclyAccessible") else "No"
            backup_r  = db.get("BackupRetentionPeriod", 0)
            latest_bk = str(db.get("LatestRestorableTime", "N/A"))[:19]
            alloc_gb  = db.get("AllocatedStorage", 0)
            if db.get("DBClusterIdentifier"):
                covered.add(db["DBClusterIdentifier"])

            dims     = [{"Name": "DBInstanceIdentifier", "Value": dbid}]
            cpu      = cw_metric(cw, "AWS/RDS", "CPUUtilization",      dims)
            free     = cw_metric(cw, "AWS/RDS", "FreeStorageSpace",    dims, stat="Minimum")
            conn     = cw_metric(cw, "AWS/RDS", "DatabaseConnections", dims)
            free_gb  = round(free / 1e9, 2) if free is not None else None
            free_pct = round((1 - free / (alloc_gb * 1e9)) * 100, 1) if (free is not None and alloc_gb) else None

            fail_events = 0
            try:
                evts = rds.describe_events(
                    SourceIdentifier=dbid, SourceType="db-instance",
                    StartTime=START_24, EndTime=NOW
                )["Events"]
                fail_events = sum(1 for e in evts
                                  if any(w in e.get("Message","").lower()
                                         for w in ["fail", "restart", "error", "crash"]))
            except Exception:
                pass

            risk_level = "Low"
            rec_parts  = []

            if pub_acc.startswith("YES"):
                risk_level = "Critical"
                rec_parts.append("DB publicly accessible — restrict to VPC only immediately.")

            if encrypt == "No":
                risk_level = max_risk(risk_level, "High")
                rec_parts.append("No encryption at rest — create encrypted snapshot and migrate.")

            if backup_r == 0:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append("Automated backups disabled — enable with 7+ day retention.")

            if multi_az == "No":
                risk_level = max_risk(risk_level, "Medium")
                rec_parts.append("Single-AZ deployment — single point of failure for production.")

            if cpu is not None and cpu > 80:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"CPU {cpu}% — add read replica or scale instance class.")

            if free_pct is not None and free_pct > 80:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"Storage {free_pct}% used — expand or enable auto-scaling.")
            elif free_gb is not None and free_gb < 5:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"Only {free_gb}GB free — critically low storage.")

            if fail_events > 0:
                risk_level = max_risk(risk_level, "High")
                rec_parts.append(f"{fail_events} error/restart events in 24h.")

            if status != "available":
                risk_level = max_risk(risk_level, "Critical")
                rec_parts.append(f"DB status '{status}' — not available.")

            if not rec_parts:
                rec_parts.append("Database healthy — no action required.")

            data = [
                dbid, engine, cls, region, az, status.upper(),
                multi_az, auto_stor,
                cpu if cpu is not None else "N/A",
                free_gb if free_gb is not None else "N/A",
                round(conn, 1) if conn is not None else "N/A",
                backup_r, latest_bk,
                encrypt, pub_acc, fail_events,
                risk_level, " | ".join(rec_parts),
            ]
            style_data_row(ws, row, len(headers))
            for i, val in enumerate(data, 1):
                ws.cell(row, i, val)
            set_risk_cell(ws, row, rl_col, risk_level)
            row += 1

        for cl in clusters:
            cid = cl["DBClusterIdentifier"]
            if cid in covered:
                continue
            engine   = f"{cl['Engine']} {cl.get('EngineVersion','')}"
            status   = cl.get("Status", "unknown")
            multi_az = "Yes" if cl.get("MultiAZ") else "No"
            backup_r = cl.get("BackupRetentionPeriod", 0)
            encrypt  = "Yes" if cl.get("StorageEncrypted") else "No"
            risk     = "Medium" if multi_az == "No" else "Low"
            data = [
                cid, engine, "Aurora Cluster", region, "Multi-AZ",
                status.upper(), multi_az, "Yes",
                "N/A", "N/A", "N/A", backup_r, "N/A",
                encrypt, "No", 0,
                risk, "Aurora cluster — review member instances for detailed metrics.",
            ]
            style_data_row(ws, row, len(headers))
            for i, val in enumerate(data, 1):
                ws.cell(row, i, val)
            set_risk_cell(ws, row, rl_col, risk)
            row += 1

    if row == 3:
        ws.cell(3, 1, "No RDS instances found across scanned regions.")

    auto_width(ws)
    ws.freeze_panes = "A3"
    ws.row_dimensions[2].height = 30
