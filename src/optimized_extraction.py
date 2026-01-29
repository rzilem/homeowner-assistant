"""
Optimized Answer Extraction Module for Manager Wizard

This module provides improved prompts and extraction logic for document Q&A.
Drop-in replacement for the extraction logic in app.py.

Usage:
    from src.optimized_extraction import extract_answer_with_claude_v2

    result = extract_answer_with_claude_v2(query, documents, community)
    # Returns dict with: found, answer, confidence, quote, source, follow_ups

Author: Claude
Created: 2026-01-28
"""

import re
import json
import logging
import requests
import os

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = "claude-3-5-haiku-20241022"  # Fast and cost-effective for extraction
MAX_TOKENS = 800

# Stop words to filter from keyword matching
STOP_WORDS = {
    'what', 'is', 'the', 'are', 'for', 'in', 'at', 'a', 'an', 'how', 'can',
    'i', 'my', 'do', 'does', 'about', 'where', 'when', 'why', 'which', 'who',
    'there', 'that', 'this', 'be', 'to', 'of', 'and', 'or', 'on', 'it'
}

# =============================================================================
# OPTIMIZED EXTRACTION PROMPT
# =============================================================================

EXTRACTION_PROMPT_V2 = """You are an expert document analyst for PS Property Management.
A community manager needs a SPECIFIC answer from HOA documents.

**QUESTION:** {query}
**COMMUNITY:** {community}

**DOCUMENTS PROVIDED:**
{doc_context}

---

## CRITICAL RULES (MUST FOLLOW):

### RULE 1: ONLY USE DOCUMENT CONTENT
- Extract answers ONLY from the text provided above
- If the answer is NOT explicitly stated, say so
- NEVER invent, assume, or infer information
- NEVER use general knowledge about HOAs

### RULE 2: BE CONCISE
- Answer in 1-2 sentences maximum (under 30 words)
- For numeric answers (heights, fees, limits): state the NUMBER first
- Example: "6 feet maximum" not "The community restricts fence heights to a maximum of six feet as outlined in the architectural guidelines"

### RULE 3: QUOTE EVIDENCE
- Include the EXACT text from the document that supports your answer
- If quoting a number, include surrounding context (5-15 words)

### RULE 4: RATE YOUR CONFIDENCE
- HIGH: Answer is explicitly stated with exact numbers/rules
- MEDIUM: Answer is implied or requires minor interpretation
- LOW: Related info found but doesn't directly answer the question

---

## RESPONSE FORMAT (STRICT JSON):

Return ONLY this JSON structure, nothing else:

{{
    "found": true,
    "answer": "Direct answer starting with the key fact. 1-2 sentences max.",
    "confidence": "high",
    "quote": "Exact text from document (5-30 words)",
    "source_document": "Filename.pdf",
    "source_section": "Article X.X or Section name",
    "answer_type": "definitive",
    "related_info": "Optional additional context",
    "follow_up_questions": ["Related question 1", "Related question 2"]
}}

If NOT found:

{{
    "found": false,
    "answer": "The specific information was not found in the available documents.",
    "confidence": "low",
    "quote": null,
    "source_document": null,
    "source_section": null,
    "answer_type": "not_found",
    "related_info": "What WAS found that's related, if anything",
    "follow_up_questions": ["Alternative answerable question 1", "Alternative answerable question 2"]
}}

---

## EXAMPLES:

QUESTION: "What is the fence height limit?"
DOCUMENT: "...Fences shall not exceed six (6) feet in height from natural grade..."

CORRECT RESPONSE:
{{
    "found": true,
    "answer": "6 feet maximum height from natural grade.",
    "confidence": "high",
    "quote": "Fences shall not exceed six (6) feet in height from natural grade",
    "source_document": "Falcon Pointe CC&Rs.pdf",
    "source_section": "Article 7.3 - Fencing",
    "answer_type": "definitive",
    "related_info": "Front yard fences may have additional restrictions.",
    "follow_up_questions": ["What fence materials are approved?", "Is ARC approval required?"]
}}

---

Return ONLY the JSON. No markdown code blocks, no explanatory text."""


# =============================================================================
# FOLLOW-UP QUESTION SUGGESTIONS
# =============================================================================

FOLLOW_UP_SUGGESTIONS = {
    'fence': [
        "What fence materials are approved?",
        "Is ARC approval required for fence installation?",
        "Can I have a fence in my front yard?",
        "What is the setback requirement for fences?",
        "Can I have a chain-link fence?"
    ],
    'pool': [
        "What are the pool guest policies?",
        "How do I get a pool key or fob?",
        "Are glass containers allowed at the pool?",
        "Can I reserve the pool area for a party?",
        "What are the pool supervision requirements?"
    ],
    'parking': [
        "How long can guests park in the community?",
        "Where is guest parking located?",
        "Can I park an RV or trailer on my property?",
        "What vehicles are prohibited?",
        "Can I park a commercial vehicle at my home?"
    ],
    'pet': [
        "How many pets are allowed per household?",
        "What is the pet weight limit?",
        "Are there breed restrictions?",
        "What are the leash requirements?",
        "Are exotic pets allowed?"
    ],
    'architectural': [
        "What modifications require ARC approval?",
        "How long does ARC approval take?",
        "What is the ARC submission process?",
        "Can I paint my house a different color?",
        "What exterior changes need approval?"
    ],
    'assessment': [
        "When are assessments due?",
        "What payment methods are accepted?",
        "Is there a late fee for overdue assessments?",
        "What does my assessment cover?",
        "Can I set up automatic payments?"
    ],
    'rental': [
        "What is the minimum lease term?",
        "Do I need to register my tenant?",
        "Are short-term rentals (Airbnb) allowed?",
        "What are landlord responsibilities?",
        "Is there a rental cap in the community?"
    ],
    'general': [
        "What are the CC&Rs for this community?",
        "How do I contact my community manager?",
        "Where can I find community documents?",
        "What is the violation process?",
        "How do I submit an ARC request?"
    ]
}

# Keywords for category detection
CATEGORY_KEYWORDS = {
    'fence': ['fence', 'fencing', 'height', 'stain', 'color', 'wrought iron', 'chain link', 'wood fence', 'privacy fence', 'barrier'],
    'pool': ['pool', 'swimming', 'hours', 'guest', 'lifeguard', 'hot tub', 'spa', 'pool key', 'pool fob', 'swim'],
    'parking': ['parking', 'vehicle', 'tow', 'rv', 'boat', 'trailer', 'commercial vehicle', 'guest parking', 'overnight', 'driveway'],
    'pet': ['pet', 'dog', 'cat', 'animal', 'breed', 'leash', 'barking', 'exotic', 'weight limit', 'pets allowed'],
    'architectural': ['arc', 'architectural', 'modification', 'approval', 'exterior', 'paint', 'roof', 'solar', 'pergola', 'deck', 'patio'],
    'rental': ['rental', 'rent', 'lease', 'tenant', 'airbnb', 'short-term', 'subletting', 'landlord', 'renter'],
    'assessment': ['assessment', 'dues', 'fee', 'payment', 'late fee', 'transfer fee', 'special assessment', 'hoa fee', 'annual fee'],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def detect_query_category(query):
    """Detect the category of a query based on keywords."""
    query_lower = query.lower()

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return 'general'


def get_follow_up_questions(query, category=None):
    """Generate relevant follow-up questions based on the query category."""
    if not category:
        category = detect_query_category(query)

    suggestions = FOLLOW_UP_SUGGESTIONS.get(category, FOLLOW_UP_SUGGESTIONS['general'])

    # Filter out questions too similar to the original query
    query_words = set(query.lower().split())
    filtered = []
    for q in suggestions:
        q_words = set(q.lower().split()[:4])
        # Skip if more than 2 words overlap with original query
        if len(q_words & query_words) <= 2:
            filtered.append(q)

    return filtered[:3]  # Return top 3 suggestions


def calculate_confidence_score(extraction_result, query, documents):
    """
    Calculate confidence score based on multiple factors.
    Returns: "high", "medium", or "low"
    """
    score = 0

    # Factor 1: Exact keyword match in quote (0-30 points)
    query_keywords = set(query.lower().split()) - STOP_WORDS
    quote = extraction_result.get('quote', '') or ''
    if quote:
        quote_lower = quote.lower()
        matches = sum(1 for kw in query_keywords if kw in quote_lower)
        score += min(30, matches * 10)

    # Factor 2: Numeric specificity (0-20 points)
    numeric_questions = ['how many', 'limit', 'height', 'fee', 'how much', 'how long', 'maximum', 'minimum']
    if any(kw in query.lower() for kw in numeric_questions):
        answer = extraction_result.get('answer', '')
        if re.search(r'\d+', answer):
            score += 20
        else:
            score -= 10  # Penalty for missing expected numbers

    # Factor 3: Source section identified (0-15 points)
    if extraction_result.get('source_section'):
        score += 15

    # Factor 4: Document relevance (0-20 points)
    source_doc = extraction_result.get('source_document', '') or ''
    doc_name = source_doc.lower()
    if 'ccr' in doc_name or 'declaration' in doc_name or 'covenant' in doc_name:
        score += 20
    elif 'rule' in doc_name or 'regulation' in doc_name:
        score += 15
    elif 'guideline' in doc_name or 'policy' in doc_name:
        score += 10
    elif doc_name:
        score += 5

    # Factor 5: Answer length appropriateness (0-15 points)
    answer = extraction_result.get('answer', '')
    word_count = len(answer.split())
    if 5 <= word_count <= 30:
        score += 15  # Concise is good
    elif word_count < 5:
        score += 5   # Too short might be incomplete
    else:
        score += 8   # Too long might be rambling

    # Convert to confidence level
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    else:
        return "low"


def build_document_context(documents, max_chars_per_doc=3000):
    """
    Build document context for the prompt, prioritizing relevant sections.
    """
    context_parts = []

    for i, doc in enumerate(documents[:5]):  # Top 5 docs
        title = doc.get('title', 'Unknown Document')
        content = doc.get('content', '').strip()
        doc_type = doc.get('doc_type_info', {}).get('label', 'Document')
        community = doc.get('community', '')
        url = doc.get('url', '')

        # Header for this document
        header = f"\n{'='*60}\nDOCUMENT {i+1}: {title}"
        if doc.get('is_archived'):
            header += " [ARCHIVED - may be outdated]"
        if community:
            header += f"\nCommunity: {community}"
        header += f"\nType: {doc_type}"
        if url:
            header += f"\nURL: {url}"

        # Truncate content intelligently
        if len(content) > max_chars_per_doc:
            content = content[:max_chars_per_doc] + "...[truncated]"

        if content:
            context_parts.append(f"{header}\n\nCONTENT:\n{content}\n")
        else:
            context_parts.append(f"{header}\n\n(No text content available)\n")

    return ''.join(context_parts)


def generate_not_found_response(query, documents_searched, category=None):
    """
    Generate a helpful response when the answer is not found.
    """
    if not category:
        category = detect_query_category(query)

    # Category-specific next steps
    next_steps = {
        'assessment': "Check your homeowner portal at psprop.net or your latest statement for current amounts.",
        'pool': "Pool hours are typically posted at the facility and may vary seasonally. Check the homeowner portal or contact your manager.",
        'architectural': "For ARC submissions and approvals, contact your community manager directly.",
        'rental': "Rental policies may have specific requirements. Contact your community manager for details.",
        'parking': "Parking policies are often enforced on-site. Check community signage or contact your manager.",
        'general': "Visit the homeowner portal at psprop.net or contact your community manager."
    }

    next_step = next_steps.get(category, next_steps['general'])

    # Get answerable follow-up questions
    follow_ups = get_follow_up_questions(query, category)

    return {
        "found": False,
        "answer": f"I couldn't find specific information about that in the available documents. {next_step}",
        "confidence": "low",
        "quote": None,
        "source_document": None,
        "source_section": None,
        "answer_type": "not_found",
        "related_info": f"Searched {len(documents_searched)} documents but no direct answer was found.",
        "recommended_action": next_step,
        "follow_up_questions": follow_ups
    }


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_answer_with_claude_v2(query, documents, community=None):
    """
    Enhanced answer extraction using Claude with confidence scoring and follow-ups.

    Args:
        query: The user's question
        documents: List of document dicts with 'title', 'content', 'url', etc.
        community: Optional community name for context

    Returns:
        dict with: found, answer, confidence, quote, source_document, source_section,
                   answer_type, related_info, follow_up_questions
        or None on error
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set")
        return None

    if not documents:
        return generate_not_found_response(query, [], detect_query_category(query))

    # Build document context
    doc_context = build_document_context(documents)

    # Format the prompt
    prompt = EXTRACTION_PROMPT_V2.format(
        query=query,
        community=community or "Not specified",
        doc_context=doc_context
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if resp.status_code != 200:
            logger.error(f"Claude API failed: {resp.status_code} - {resp.text[:200]}")
            return None

        content = resp.json()['content'][0]['text']

        # Parse JSON response
        try:
            # Find JSON in response (handles markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())

                # Validate and enhance result
                if not result.get('answer'):
                    result['answer'] = "No specific information found in the available documents."
                    result['found'] = False

                # Calculate confidence if not provided or validate existing
                if 'confidence' not in result or result['confidence'] not in ['high', 'medium', 'low']:
                    result['confidence'] = calculate_confidence_score(result, query, documents)

                # Add follow-up questions if not provided
                if 'follow_up_questions' not in result or not result['follow_up_questions']:
                    result['follow_up_questions'] = get_follow_up_questions(query)

                # Ensure all expected fields exist
                result.setdefault('found', False)
                result.setdefault('quote', None)
                result.setdefault('source_document', None)
                result.setdefault('source_section', None)
                result.setdefault('answer_type', 'definitive' if result.get('found') else 'not_found')
                result.setdefault('related_info', None)

                # Add extraction metadata
                result['extraction_type'] = detect_query_category(query)

                return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude JSON response: {e}")
            logger.debug(f"Raw response: {content[:500]}")

        return None

    except requests.exceptions.Timeout:
        logger.error("Claude API timeout")
        return None
    except Exception as e:
        logger.error(f"Claude extraction failed: {e}")
        return None


# =============================================================================
# MULTI-DOCUMENT SYNTHESIS
# =============================================================================

SYNTHESIS_PROMPT = """You are synthesizing information from MULTIPLE HOA documents.

**QUESTION:** {query}
**COMMUNITY:** {community}

**DOCUMENTS:**
{doc_summaries}

---

## YOUR TASK:
1. Identify ALL relevant information across documents
2. Combine into a SINGLE coherent answer (under 50 words)
3. Note if documents conflict (newer takes precedence)
4. Cite which document each key fact comes from

## RESPONSE FORMAT (JSON):
{{
    "found": true,
    "answer": "Synthesized answer",
    "confidence": "high/medium/low",
    "sources": [
        {{"document": "Doc name", "contribution": "What this doc added", "quote": "Exact text"}}
    ],
    "conflicts_found": false,
    "conflict_note": null,
    "follow_up_questions": ["Question 1", "Question 2"]
}}

Return ONLY JSON."""


def synthesize_multiple_documents(query, documents, community=None):
    """
    Synthesize answers from multiple documents that all contain relevant info.
    Use when 2+ documents have matching content.
    """
    if not ANTHROPIC_API_KEY or len(documents) < 2:
        return None

    # Build summaries of each document
    doc_summaries = []
    for i, doc in enumerate(documents[:5]):
        title = doc.get('title', 'Unknown')
        content = doc.get('content', '')[:2000]
        doc_summaries.append(f"[{i+1}] {title}\n{content}\n")

    prompt = SYNTHESIS_PROMPT.format(
        query=query,
        community=community or "Not specified",
        doc_summaries='\n'.join(doc_summaries)
    )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if resp.status_code == 200:
            content = resp.json()['content'][0]['text']
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())

        return None

    except Exception as e:
        logger.error(f"Document synthesis failed: {e}")
        return None


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Quick test
    test_docs = [
        {
            "title": "Falcon Pointe CC&Rs.pdf",
            "content": "Article 7.3 - Fencing. No fence shall exceed six (6) feet in height from natural grade. All fences require ARC approval prior to installation. Approved materials include wood, wrought iron, and vinyl.",
            "url": "https://example.com/ccr.pdf",
            "doc_type_info": {"label": "CC&Rs"}
        }
    ]

    result = extract_answer_with_claude_v2(
        query="What is the fence height limit at Falcon Pointe?",
        documents=test_docs,
        community="Falcon Pointe"
    )

    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Extraction failed")
