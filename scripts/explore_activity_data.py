"""
Explore Power BI datasets to find homeowner activity data:
- General Inquiries
- Billing Inquiries
- ARC Applications
- Recent Calls
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

# Datasets to explore
DATASETS = {
    'M360': {
        'workspace': 'c5395f33-bd22-4d26-846f-5ad44c7ad108',
        'dataset': 'e17e4241-37b7-4d12-a2e8-8f4e6148ca03'
    },
    'KPI': {
        'workspace': '7def987c-e21b-4349-ac0f-731a4cf542d9',
        'dataset': '1d0f8dce-cebc-4a87-9d4a-32aa04af03c7'
    }
}

def run_dax(workspace_id, dataset_id, query, label=""):
    """Execute DAX query and return rows."""
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        return resp.json()['results'][0]['tables'][0]['rows']
    else:
        print(f"    [{label}] Error {resp.status_code}: {resp.text[:200]}")
        return None

print("=" * 70)
print("EXPLORING POWER BI FOR HOMEOWNER ACTIVITY DATA")
print("=" * 70)

# 1. Check ActionItemDetails columns
print("\n[1] ActionItemDetails Table - Columns:")
for name, ds in DATASETS.items():
    rows = run_dax(ds['workspace'], ds['dataset'],
        "EVALUATE TOPN(1, ActionItemDetails)", f"{name} ActionItemDetails")
    if rows:
        cols = list(rows[0].keys())
        print(f"\n    {name} - {len(cols)} columns:")
        for c in sorted(cols):
            print(f"        {c}")

# 2. Find all action item types
print("\n" + "=" * 70)
print("[2] Action Item Types (ai_TypeDescr values):")
for name, ds in DATASETS.items():
    query = """
    EVALUATE
    SUMMARIZECOLUMNS(
        ActionItemDetails[ai_TypeDescr],
        "Count", COUNTROWS(ActionItemDetails)
    )
    ORDER BY [Count] DESC
    """
    rows = run_dax(ds['workspace'], ds['dataset'], query, f"{name} Types")
    if rows:
        print(f"\n    {name} Dataset:")
        for row in rows[:30]:  # Top 30 types
            type_name = row.get('ActionItemDetails[ai_TypeDescr]', 'Unknown')
            count = row.get('[Count]', 0)
            # Highlight relevant types
            highlight = ""
            if any(x in str(type_name).lower() for x in ['inquiry', 'call', 'arc', 'billing', 'phone']):
                highlight = " <-- RELEVANT"
            print(f"        {type_name}: {count:,}{highlight}")

# 3. Look for call/phone related tables
print("\n" + "=" * 70)
print("[3] Looking for Call/Phone Tables:")
call_tables = ['Calls', 'PhoneCalls', 'CallLog', 'pstn_calls', 'PhoneLog', 'ContactLog']
for name, ds in DATASETS.items():
    print(f"\n    {name} Dataset:")
    for table in call_tables:
        query = f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))"
        rows = run_dax(ds['workspace'], ds['dataset'], query, table)
        if rows:
            count = list(rows[0].values())[0]
            print(f"        FOUND: '{table}' with {count:,} rows")

# 4. Sample ActionItemDetails for relevant types
print("\n" + "=" * 70)
print("[4] Sample Records for Relevant Types:")

relevant_types = ['General Inquiry', 'Billing Inquiry', 'ARC', 'Phone Call', 'Inbound Call']
for name, ds in DATASETS.items():
    for item_type in relevant_types:
        query = f"""
        EVALUATE
        TOPN(2,
            FILTER(ActionItemDetails,
                SEARCH("{item_type}", ActionItemDetails[ai_TypeDescr], 1, 0) > 0
            )
        )
        """
        rows = run_dax(ds['workspace'], ds['dataset'], query, f"{name} {item_type}")
        if rows:
            print(f"\n    {name} - '{item_type}' sample:")
            for k, v in rows[0].items():
                if v:
                    val_str = str(v)[:60]
                    print(f"        {k}: {val_str}")

# 5. Check if there's an account/owner link field
print("\n" + "=" * 70)
print("[5] Owner/Account Link Fields in ActionItemDetails:")
for name, ds in DATASETS.items():
    rows = run_dax(ds['workspace'], ds['dataset'],
        "EVALUATE TOPN(1, ActionItemDetails)", f"{name}")
    if rows:
        cols = list(rows[0].keys())
        link_cols = [c for c in cols if any(x in c.lower() for x in
            ['owner', 'account', 'acct', 'ownerid', 'accountid', 'propid', 'property'])]
        print(f"\n    {name} - Potential link columns:")
        for c in link_cols:
            sample_val = rows[0].get(c, 'N/A')
            print(f"        {c}: {sample_val}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
