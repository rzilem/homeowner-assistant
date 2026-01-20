"""
Explore Power BI KPI dataset for homeowner activity data.
Uses correct column names found in exploration.
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

# KPI Dataset
WORKSPACE = '7def987c-e21b-4349-ac0f-731a4cf542d9'
DATASET = '1d0f8dce-cebc-4a87-9d4a-32aa04af03c7'

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
        print(f"    [{label}] Error {resp.status_code}: {resp.text[:300]}")
        return None

print("=" * 70)
print("EXPLORING KPI DATASET FOR ACTIVITY DATA")
print("=" * 70)

# 1. Get all Action Types
print("\n[1] All Action Types (ActionTypeDescr):")
query = """
EVALUATE
SUMMARIZECOLUMNS(
    ActionItemDetails[ActionTypeDescr],
    "Count", COUNTROWS(ActionItemDetails)
)
ORDER BY [Count] DESC
"""
rows = run_dax(query, "Action Types")
if rows:
    for row in rows:
        type_name = row.get('ActionItemDetails[ActionTypeDescr]', 'Unknown')
        count = row.get('[Count]', 0)
        # Highlight relevant types
        highlight = ""
        if any(x in str(type_name).lower() for x in ['inquiry', 'call', 'arc', 'billing', 'phone', 'request']):
            highlight = " <-- RELEVANT"
        print(f"    {type_name}: {count:,}{highlight}")

# 2. Get all Action Categories
print("\n[2] All Action Categories:")
query = """
EVALUATE
SUMMARIZECOLUMNS(
    ActionItemDetails[ActionCategoryDescription],
    "Count", COUNTROWS(ActionItemDetails)
)
ORDER BY [Count] DESC
"""
rows = run_dax(query, "Categories")
if rows:
    for row in rows:
        cat = row.get('ActionItemDetails[ActionCategoryDescription]', 'Unknown')
        count = row.get('[Count]', 0)
        print(f"    {cat}: {count:,}")

# 3. Sample a few records to see all fields
print("\n[3] Sample Record (all fields):")
query = "EVALUATE TOPN(1, ActionItemDetails)"
rows = run_dax(query, "Sample")
if rows:
    for k, v in rows[0].items():
        print(f"    {k}: {v}")

# 4. Look for other tables that might have owner-level data
print("\n[4] Looking for Owner-Level Activity Tables:")
tables_to_try = [
    'OwnerActionItems', 'PropertyActionItems', 'OwnerActivity',
    'ActivityLog', 'OwnerHistory', 'ContactHistory', 'OwnerNotes',
    'Notes', 'OwnerContacts', 'ServiceRequests', 'ARCRequests',
    'ARC', 'ARCApplications', 'Inquiries', 'BillingInquiries',
    'GeneralInquiries', 'vOwnerActionItems', 'vwOwnerActivity'
]
for table in tables_to_try:
    query = f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))"
    rows = run_dax(query, table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    FOUND: '{table}' with {count:,} rows")

# 5. List ALL tables in the dataset
print("\n[5] Trying to find all tables via INFO functions:")
# Try different approaches to list tables
info_queries = [
    ("INFO.TABLES()", "INFO.TABLES"),
]
for q, label in info_queries:
    query = f"EVALUATE {q}"
    rows = run_dax(query, label)
    if rows:
        print(f"    {label} worked! Tables found:")
        for row in rows:
            print(f"        {row}")

# 6. Check if there's a way to link ActionItemDetails to owners
print("\n[6] Check for Owner Link in ActionItemDetails:")
# See if there's any field that could link to an owner
query = """
EVALUATE
TOPN(5,
    SELECTCOLUMNS(ActionItemDetails,
        "AssocID", ActionItemDetails[AssocID],
        "AssocName", ActionItemDetails[AssocName],
        "ActionType", ActionItemDetails[ActionTypeDescr],
        "Category", ActionItemDetails[ActionCategoryDescription],
        "Created", ActionItemDetails[ActionItemCreatedDate],
        "Note", ActionItemDetails[LastNote]
    )
)
"""
rows = run_dax(query, "Sample with key fields")
if rows:
    print("    Sample records:")
    for i, row in enumerate(rows):
        print(f"\n    Record {i+1}:")
        for k, v in row.items():
            val = str(v)[:80] if v else 'N/A'
            print(f"        {k}: {val}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
