"""
Document Classifier for Azure AI Search
Classifies SharePoint documents by category and access level.

Categories:
- owner_*: Individual homeowner documents
- governing_*: CC&Rs, bylaws, rules
- community_*: Minutes, newsletters, announcements
- board_*: Financial, contracts, legal
- staff_*: Bids, violations, work orders

Access Levels:
- owner_only: Specific homeowner + staff
- community_public: Community members + board + staff
- board_only: Board + staff
- staff_only: Staff only

Usage:
    python classify_documents.py              # Classify all unclassified docs
    python classify_documents.py --all        # Reclassify everything
    python classify_documents.py --dry-run    # Preview without updating
    python classify_documents.py --stats      # Show classification stats
"""

import os
import re
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import requests

# Azure AI Search configuration
SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_ENDPOINT', 'https://psmai.search.windows.net')
SEARCH_API_KEY = os.getenv('AZURE_SEARCH_API_KEY')  # Required - set in environment
INDEX_NAME = 'sharepoint-docs'
API_VERSION = '2024-05-01-preview'

# =============================================================================
# CLASSIFICATION RULES
# =============================================================================

# Pattern-based classification rules (order matters - first match wins)
CLASSIFICATION_RULES = [
    # OWNER DOCUMENTS - owner_only access
    {
        'category': 'owner_statement',
        'access_level': 'owner_only',
        'patterns': {
            'path': [r'/Statement/', r'/Statements/', r'/Billing/'],
            'name': [r'^\d+.*statement', r'statement.*\.pdf$', r'^R\d+L\d+']
        }
    },
    {
        'category': 'owner_ledger',
        'access_level': 'owner_only',
        'patterns': {
            'path': [r'/Ledger/', r'/Account History/'],
            'name': [r'ledger', r'account.*history']
        }
    },
    {
        'category': 'owner_letter',
        'access_level': 'owner_only',
        'patterns': {
            'path': [r'/Owner Letters/', r'/Homeowner Letters/'],
            'name': [r'letter.*to.*', r'demand.*letter', r'collection.*letter', r'notice.*to.*owner']
        }
    },
    {
        'category': 'owner_arc_submission',
        'access_level': 'arc_review',
        'patterns': {
            'path': [r'/ARC.*Submission/', r'/ARC.*Application/', r'/Architectural.*Request/'],
            'name': [r'arc.*application', r'arc.*request', r'architectural.*submission']
        }
    },

    # GOVERNING DOCUMENTS - community_public access
    {
        'category': 'governing_ccr',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Govern/', r'/Governing/', r'/CCR/'],
            'name': [r'ccr', r'cc&r', r'covenants?', r'declaration', r'deed.*restriction', r'restrictions']
        }
    },
    {
        'category': 'governing_bylaws',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Govern/', r'/Governing/', r'/Bylaws/'],
            'name': [r'bylaw', r'by-law', r'by\s+law']
        }
    },
    {
        'category': 'governing_rules',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Govern/', r'/Governing/', r'/Rules/'],
            'name': [r'rules?.*regulation', r'regulation', r'policies', r'policy(?!.*insurance)', r'guidelines?(?!.*arc)']
        }
    },
    {
        'category': 'governing_arc_guidelines',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/ARC/', r'/Architectural/', r'/Design/'],
            'name': [r'arc.*guide', r'architectural.*guide', r'architectural.*standard', r'design.*guide', r'design.*standard']
        }
    },

    # COMMUNITY DOCUMENTS - community_public access (except directory)
    {
        'category': 'community_minutes',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Minutes/', r'/Meeting Minutes/', r'/Board Meeting/'],
            'name': [r'minutes', r'meeting.*notes', r'board.*meeting']
        }
    },
    {
        'category': 'community_newsletter',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Newsletter/', r'/Communications/'],
            'name': [r'newsletter', r'bulletin', r'community.*update']
        }
    },
    {
        'category': 'community_announcement',
        'access_level': 'community_public',
        'patterns': {
            'path': [r'/Notices/', r'/Announcements/'],
            'name': [r'announcement', r'notice(?!.*violation)', r'alert', r'advisory']
        }
    },
    {
        'category': 'community_directory',
        'access_level': 'board_only',  # NOT public - contains contact info
        'patterns': {
            'path': [r'/Directory/', r'/Contact/'],
            'name': [r'directory', r'contact.*list', r'phone.*list', r'resident.*list']
        }
    },

    # BOARD DOCUMENTS - board_only access
    {
        'category': 'board_financial',
        'access_level': 'board_only',
        'patterns': {
            'path': [r'/Financial/', r'/Budget/', r'/Audit/', r'/Reserve/'],
            'name': [r'budget', r'financial.*statement', r'balance.*sheet', r'income.*statement',
                    r'audit', r'reserve.*study', r'reserve.*analysis', r'bank.*statement']
        }
    },
    {
        'category': 'board_delinquency',
        'access_level': 'board_only',
        'patterns': {
            'path': [r'/Delinquency/', r'/Collections/', r'/Aging/'],
            'name': [r'delinquen', r'aging.*report', r'collection.*report', r'past.*due']
        }
    },
    {
        'category': 'board_insurance',
        'access_level': 'board_only',
        'patterns': {
            'path': [r'/Insurance/'],
            'name': [r'insurance.*polic', r'certificate.*insurance', r'coi', r'coverage', r'liability.*policy']
        }
    },
    {
        'category': 'board_contracts',
        'access_level': 'board_only',
        'patterns': {
            'path': [r'/Contract/', r'/Agreement/', r'/Service Agreement/'],
            'name': [r'contract', r'agreement(?!.*arc)', r'service.*contract', r'maintenance.*agreement']
        }
    },
    {
        'category': 'board_legal',
        'access_level': 'board_only',
        'patterns': {
            'path': [r'/Legal/', r'/Attorney/', r'/Litigation/'],
            'name': [r'legal', r'attorney', r'lawsuit', r'litigation', r'lien(?!.*release)', r'judgment', r'court']
        }
    },

    # STAFF DOCUMENTS - staff_only access
    {
        'category': 'staff_bids',
        'access_level': 'staff_only',
        'patterns': {
            'path': [r'/Bid/', r'/Bids/', r'/Proposal/', r'/Proposals/', r'/Quote/'],
            'name': [r'bid', r'proposal', r'estimate', r'quote', r'pricing']
        }
    },
    {
        'category': 'staff_violations',
        'access_level': 'staff_only',
        'patterns': {
            'path': [r'/Violation/', r'/Compliance/'],
            'name': [r'violation', r'compliance.*notice', r'warning.*letter', r'fine.*notice']
        }
    },
    {
        'category': 'staff_work_orders',
        'access_level': 'staff_only',
        'patterns': {
            'path': [r'/Work.*Order/', r'/Maintenance.*Request/', r'/Service.*Request/'],
            'name': [r'work.*order', r'service.*request', r'maintenance.*request', r'repair.*request']
        }
    },
    {
        'category': 'staff_correspondence',
        'access_level': 'staff_only',
        'patterns': {
            'path': [r'/Internal/', r'/Staff.*Notes/', r'/Correspondence/'],
            'name': [r'internal.*memo', r'staff.*note', r'correspondence(?!.*owner)']
        }
    },
    {
        'category': 'staff_vendor',
        'access_level': 'staff_only',
        'patterns': {
            'path': [r'/Vendor/', r'/W9/', r'/W-9/'],
            'name': [r'w-?9', r'vendor.*info', r'vendor.*contact', r'vendor.*setup']
        }
    },
]

# Community name extraction patterns
COMMUNITY_PATTERNS = [
    # Office/Community/... structure
    r'/(?:Round Rock|North Austin|South Austin) Office/([^/]+)/',
    # Direct community folder
    r'/sites/AssociationDocs/([^/]+)/',
]

# Owner account ID extraction patterns (from statement filenames)
OWNER_ACCOUNT_PATTERNS = [
    r'^(R\d+L\d+)',  # R0460131L0199873 format
    r'Account[:\s#]*(\d+)',
    r'Acct[:\s#]*(\d+)',
]


def classify_document(path: str, name: str) -> Tuple[str, str]:
    """
    Classify a document based on its path and name.
    Returns (category, access_level)
    """
    path_lower = path.lower() if path else ''
    name_lower = name.lower() if name else ''

    for rule in CLASSIFICATION_RULES:
        matched = False

        # Check path patterns
        for pattern in rule['patterns'].get('path', []):
            if re.search(pattern, path_lower, re.IGNORECASE):
                matched = True
                break

        # Check name patterns
        if not matched:
            for pattern in rule['patterns'].get('name', []):
                if re.search(pattern, name_lower, re.IGNORECASE):
                    matched = True
                    break

        if matched:
            return rule['category'], rule['access_level']

    # Default: uncategorized, staff only
    return 'uncategorized', 'staff_only'


def extract_community_name(path: str) -> Optional[str]:
    """Extract community name from document path."""
    if not path:
        return None

    for pattern in COMMUNITY_PATTERNS:
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            community = match.group(1)
            # Clean up community name
            community = community.replace('%20', ' ')
            community = re.sub(r'\s+', ' ', community).strip()
            return community

    return None


def extract_owner_account(name: str, path: str) -> Optional[str]:
    """Extract owner account ID from document name or path."""
    text = f"{name} {path}" if path else name

    for pattern in OWNER_ACCOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def search_documents(skip: int = 0, top: int = 1000, unclassified_only: bool = True) -> List[Dict]:
    """Fetch documents from Azure Search index."""
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"

    body = {
        "search": "*",
        "skip": skip,
        "top": top,
        "select": "id,metadata_spo_item_name,metadata_spo_item_path,document_category,community_name",
        "count": True
    }

    if unclassified_only:
        body["filter"] = "document_category eq null or document_category eq ''"

    response = requests.post(url, json=body, headers={
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY
    })

    if response.status_code != 200:
        print(f"Error searching: {response.status_code} - {response.text}")
        return []

    data = response.json()
    return data.get('value', []), data.get('@odata.count', 0)


def update_document(doc_id: str, updates: Dict) -> bool:
    """Update a single document in the index."""
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"

    body = {
        "value": [{
            "@search.action": "merge",
            "id": doc_id,
            **updates
        }]
    }

    response = requests.post(url, json=body, headers={
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY
    })

    return response.status_code == 200


def update_documents_batch(updates: List[Dict]) -> Tuple[int, int]:
    """Update multiple documents in a batch."""
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"

    body = {
        "value": [{"@search.action": "merge", **doc} for doc in updates]
    }

    response = requests.post(url, json=body, headers={
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY
    })

    if response.status_code == 200:
        result = response.json()
        succeeded = sum(1 for r in result.get('value', []) if r.get('status'))
        failed = len(updates) - succeeded
        return succeeded, failed
    else:
        print(f"Batch update error: {response.status_code} - {response.text}")
        return 0, len(updates)


def get_classification_stats() -> Dict:
    """Get current classification statistics."""
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"

    # Get category facets
    body = {
        "search": "*",
        "top": 0,
        "facets": ["document_category,count:50", "access_level,count:10"],
        "count": True
    }

    response = requests.post(url, json=body, headers={
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY
    })

    if response.status_code != 200:
        return {}

    data = response.json()

    return {
        "total_documents": data.get('@odata.count', 0),
        "by_category": {f['value']: f['count'] for f in data.get('@search.facets', {}).get('document_category', [])},
        "by_access_level": {f['value']: f['count'] for f in data.get('@search.facets', {}).get('access_level', [])}
    }


def run_classification(reclassify_all: bool = False, dry_run: bool = False, batch_size: int = 100):
    """Run document classification."""
    print("=" * 60)
    print("Document Classification")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Scope: {'All documents' if reclassify_all else 'Unclassified only'}")
    print()

    # Get total count
    _, total_count = search_documents(skip=0, top=1, unclassified_only=not reclassify_all)
    print(f"Documents to process: {total_count}")
    print()

    if total_count == 0:
        print("No documents to classify!")
        return

    # Classification counters
    stats = {
        'processed': 0,
        'updated': 0,
        'failed': 0,
        'by_category': {},
        'by_access_level': {}
    }

    skip = 0
    batch_updates = []

    while skip < total_count:
        docs, _ = search_documents(skip=skip, top=batch_size, unclassified_only=not reclassify_all)

        if not docs:
            break

        for doc in docs:
            doc_id = doc.get('id')
            name = doc.get('metadata_spo_item_name', '')
            path = doc.get('metadata_spo_item_path', '')

            # Classify
            category, access_level = classify_document(path, name)
            community = extract_community_name(path) or doc.get('community_name')
            owner_account = None

            # Extract owner account for owner documents
            if category.startswith('owner_'):
                owner_account = extract_owner_account(name, path)

            # Prepare update
            update = {
                'id': doc_id,
                'document_category': category,
                'access_level': access_level,
                'classified_at': datetime.utcnow().isoformat() + 'Z'
            }

            if community:
                update['community_name'] = community
            if owner_account:
                update['owner_account_id'] = owner_account

            batch_updates.append(update)

            # Track stats
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
            stats['by_access_level'][access_level] = stats['by_access_level'].get(access_level, 0) + 1

            # Show sample
            if stats['processed'] < 10:
                print(f"  [{category}] {name[:50]}...")

            stats['processed'] += 1

        # Batch update
        if not dry_run and len(batch_updates) >= batch_size:
            succeeded, failed = update_documents_batch(batch_updates)
            stats['updated'] += succeeded
            stats['failed'] += failed
            batch_updates = []
            print(f"  Progress: {stats['processed']}/{total_count} ({100*stats['processed']//total_count}%)")

        skip += batch_size

    # Final batch
    if not dry_run and batch_updates:
        succeeded, failed = update_documents_batch(batch_updates)
        stats['updated'] += succeeded
        stats['failed'] += failed

    # Print results
    print()
    print("=" * 60)
    print("Classification Results")
    print("=" * 60)
    print(f"Total processed: {stats['processed']}")
    if not dry_run:
        print(f"Successfully updated: {stats['updated']}")
        print(f"Failed: {stats['failed']}")
    print()
    print("By Category:")
    for cat, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print()
    print("By Access Level:")
    for level, count in sorted(stats['by_access_level'].items(), key=lambda x: -x[1]):
        print(f"  {level}: {count}")


def show_stats():
    """Show current classification statistics."""
    print("=" * 60)
    print("Current Classification Statistics")
    print("=" * 60)

    stats = get_classification_stats()

    print(f"\nTotal documents: {stats.get('total_documents', 0)}")

    print("\nBy Category:")
    by_cat = stats.get('by_category', {})
    if by_cat:
        for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"  {cat or '(unclassified)'}: {count}")
    else:
        print("  No classification data yet")

    print("\nBy Access Level:")
    by_level = stats.get('by_access_level', {})
    if by_level:
        for level, count in sorted(by_level.items(), key=lambda x: -x[1]):
            print(f"  {level or '(none)'}: {count}")
    else:
        print("  No access level data yet")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify SharePoint documents in Azure AI Search")
    parser.add_argument("--all", action="store_true", help="Reclassify all documents (not just unclassified)")
    parser.add_argument("--dry-run", action="store_true", help="Preview classification without updating")
    parser.add_argument("--stats", action="store_true", help="Show current classification statistics")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for updates")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_classification(
            reclassify_all=args.all,
            dry_run=args.dry_run,
            batch_size=args.batch_size
        )
