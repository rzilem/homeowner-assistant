"""
Explore M360 dataset for owner-level activity data.
The 'pbi Homeowners' table exists here - check for related activity tables.
"""
import json
import requests
import msal

# Load config
config_path = r'C:\Users\ricky\OneDrive - PS Prop Mgmt\Documents\GitHub\board-weekly-updates\config.json'
with open(config_path) as f:
    config = json.load(f)

pbi = config['power_bi']

# Get Power BI token
app = msal.ConfidentialClientApplication(
    pbi['client_id'],
    authority=f"https://login.microsoftonline.com/{pbi['tenant_id']}",
    client_credential=pbi['client_secret']
)
result = app.acquire_token_for_client(
    scopes=["https://analysis.windows.net/powerbi/api/.default"]
)
token = result['access_token']
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# M360 Dataset (same as homeowner sync)
WORKSPACE = pbi['m360_workspace_id']
DATASET = pbi['m360_dataset_id']

def run_dax(query, label=""):
    """Execute DAX query and return rows."""
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE}/datasets/{DATASET}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        return resp.json()['results'][0]['tables'][0]['rows']
    else:
        print(f"    [{label}] Error {resp.status_code}: {resp.text[:200]}")
        return None

print("=" * 70)
print("EXPLORING M360 DATASET FOR OWNER-LEVEL ACTIVITY")
print(f"Workspace: {WORKSPACE}")
print(f"Dataset: {DATASET}")
print("=" * 70)

# 1. Try to find activity tables with owner links
print("\n[1] Looking for Activity Tables with Owner Data:")
activity_tables = [
    'pbi OwnerActivity', 'OwnerActivity', 'pbi Inquiries', 'Inquiries',
    'pbi GeneralInquiry', 'GeneralInquiry', 'pbi ActionItems', 'ActionItems',
    'pbi OwnerActionItems', 'OwnerActionItems', 'pbi Notes', 'Notes',
    'pbi OwnerNotes', 'OwnerNotes', 'pbi Calls', 'Calls',
    'pbi ARC', 'ARC', 'pbi ARCRequests', 'ARCRequests',
    'vwOwnerActivity', 'vwActionItems', 'vwInquiries',
    'Owner Activity', 'Action Items', 'Owner Notes'
]

found_tables = []
for table in activity_tables:
    query = f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))"
    rows = run_dax(query, table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    FOUND: '{table}' with {count:,} rows")
        found_tables.append(table)

# 2. Check columns in pbi Homeowners - maybe activity is embedded
print("\n[2] All columns in 'pbi Homeowners':")
query = "EVALUATE TOPN(1, 'pbi Homeowners')"
rows = run_dax(query, "pbi Homeowners sample")
if rows:
    cols = list(rows[0].keys())
    print(f"    Found {len(cols)} columns:")
    for c in sorted(cols):
        val = rows[0].get(c)
        val_str = str(val)[:50] if val else 'NULL'
        # Highlight activity-related columns
        highlight = ""
        if any(x in c.lower() for x in ['inquiry', 'arc', 'call', 'note', 'activity', 'contact']):
            highlight = " <-- ACTIVITY?"
        print(f"        {c}: {val_str}{highlight}")

# 3. Check ActionItemDetails in M360 for owner link
print("\n[3] ActionItemDetails in M360 - checking for owner fields:")
query = "EVALUATE TOPN(1, ActionItemDetails)"
rows = run_dax(query, "ActionItemDetails")
if rows:
    cols = list(rows[0].keys())
    owner_cols = [c for c in cols if any(x in c.lower() for x in
        ['owner', 'property', 'account', 'propid', 'ownerid', 'acct'])]
    print(f"    Potential owner link columns: {owner_cols}")
    print(f"    All columns ({len(cols)}):")
    for c in sorted(cols):
        print(f"        {c}")

# 4. Check if there's a relationship - ActionItemDetails linked to owners
print("\n[4] Checking for ActionItemDetails with Owner/Property ID:")
query = """
EVALUATE
SELECTCOLUMNS(
    TOPN(5, ActionItemDetails),
    "All columns", ActionItemDetails[ActionItemID]
)
"""
# Try to see if there's an OwnerID or PropertyID column
test_cols = ['OwnerID', 'PropertyID', 'PropID', 'OwnerAcctNo', 'AccountNo', 'AcctNo']
for col in test_cols:
    query = f"""
    EVALUATE
    TOPN(3,
        SELECTCOLUMNS(ActionItemDetails,
            "ID", ActionItemDetails[ActionItemID],
            "Type", ActionItemDetails[ActionTypeDescr],
            "LinkCol", ActionItemDetails[{col}]
        )
    )
    """
    rows = run_dax(query, f"ActionItemDetails.{col}")
    if rows:
        print(f"\n    FOUND column ActionItemDetails[{col}]!")
        for row in rows:
            print(f"        {row}")

# 5. Look for any table with "Owner" in the name
print("\n[5] Looking for any table with 'Owner' or 'Property' in name:")
owner_tables = [
    'pbi Owners', 'Owners', 'Owner', 'pbi Owner',
    'OwnerLedger', 'pbi OwnerLedger', 'vOwnerLedger', 'vOwnerLedger2',
    'OwnerContacts', 'pbi OwnerContacts', 'PropertyOwners',
    'OwnerHistory', 'OwnerCommunications'
]
for table in owner_tables:
    query = f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))"
    rows = run_dax(query, table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    FOUND: '{table}' with {count:,} rows")
        # Get sample columns
        query2 = f"EVALUATE TOPN(1, '{table}')"
        rows2 = run_dax(query2, f"{table} columns")
        if rows2:
            cols = list(rows2[0].keys())
            print(f"        Columns: {cols[:10]}...")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
