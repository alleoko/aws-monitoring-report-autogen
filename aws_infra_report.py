import openpyxl
from sheets.common         import NOW, TS_LABEL
from sheets.sheet_summary  import build_summary_sheet
from sheets.sheet_ec2      import build_ec2_sheet
from sheets.sheet_ecs      import build_ecs_sheet
from sheets.sheet_rds      import build_rds_sheet
from sheets.sheet_security import build_security_sheet
from sheets.sheet_cost     import build_cost_sheet
from sheets.sheet_alarms   import build_alarms_sheet
from sheets.sheet_alb      import build_alb_sheet
from sheets.sheet_ebs      import build_ebs_sheet
from sheets.sheet_asg      import build_asg_sheet


def main():
    print(f"[{TS_LABEL}] Starting AWS infrastructure data collection...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    print("  [1/9] Executive Summary...")
    build_summary_sheet(wb)

    print("  [2/9] EC2 Health...")
    build_ec2_sheet(wb)

    print("  [3/9] ECS Clusters...")
    build_ecs_sheet(wb)

    print("  [4/9] RDS Health...")
    build_rds_sheet(wb)

    print("  [5/9] Security Posture...")
    build_security_sheet(wb)

    print("  [6/9] Cost & Utilization...")
    build_cost_sheet(wb)

    print("  [7/9] CloudWatch Alarms...")
    build_alarms_sheet(wb)

    print("  [8/9] Load Balancers...")
    build_alb_sheet(wb)

    print("  [9/9] EBS Volumes...")
    build_ebs_sheet(wb)

    print("  [+]   Auto Scaling Groups...")
    build_asg_sheet(wb)

    filename = f"AWS_Infra_Report_{NOW.strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = rf"C:\Users\123\Daily Monitoring Report\{filename}"
    wb.save(filepath)
    print(f"\n  Report saved: {filepath}")
    print(f"  Sheets: {[s.title for s in wb.worksheets]}")
    return filepath


if __name__ == "__main__":
    main()
