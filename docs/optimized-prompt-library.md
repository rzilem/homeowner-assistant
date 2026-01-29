# Optimized Prompt Library for Document Q&A

## Executive Summary

This document provides an optimized prompt library to improve document Q&A answer extraction from **59% "found" rate to 75%+**. The improvements focus on:

1. **Better answer extraction** - More precise prompts that reduce verbosity
2. **Confidence scoring** - AI rates its own confidence (high/medium/low)
3. **Improved "not found" handling** - Helpful responses when answer isn't in documents
4. **Source attribution** - Always cite exact document and section
5. **Multi-document synthesis** - Combine info from multiple sources
6. **Follow-up suggestions** - Suggest related questions

---

## Current Issues Identified

| Issue | Impact | Solution |
|-------|--------|----------|
| Answers too verbose | Users get 200+ word responses when 20 words suffice | Strict word limits in prompts |
| Hallucination when not found | AI invents plausible-sounding rules | Explicit "ONLY from document" instruction |
| Missing exact quotes | Claims without textual evidence | Required quote field in JSON output |
| No confidence indication | Users can't gauge reliability | Confidence scoring (high/medium/low) |
| Generic "not found" responses | Unhelpful for users | Contextual fallback with next steps |
| Single document focus | Misses info spread across docs | Multi-document synthesis prompt |

---

## Prompt Library

### 1. Primary Answer Extraction Prompt (Manager Wizard)

```python
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
- Answer in 1-2 sentences maximum
- For numeric answers (heights, fees, limits): state the NUMBER first
- Example: "6 feet maximum" not "The community restricts fence heights to a maximum of six feet as outlined in the architectural guidelines"

### RULE 3: QUOTE EVIDENCE
- Include the EXACT text from the document that supports your answer
- If quoting a number, include surrounding context

### RULE 4: RATE YOUR CONFIDENCE
- HIGH: Answer is explicitly stated with exact numbers/rules
- MEDIUM: Answer is implied or requires minor interpretation
- LOW: Related info found but doesn't directly answer the question

---

## RESPONSE FORMAT (JSON ONLY):

```json
{{
    "found": true/false,
    "answer": "Direct answer in 1-2 sentences. Start with the key fact.",
    "confidence": "high/medium/low",
    "quote": "Exact text from document supporting this answer",
    "source_document": "Name of document where answer was found",
    "source_section": "Section or article number if available (e.g., 'Article 5.3')",
    "answer_type": "definitive/partial/not_found",
    "related_info": "Any additional relevant context (optional)",
    "follow_up_questions": ["Suggested related question 1", "Suggested related question 2"]
}}
```

---

## EXAMPLES:

### Example 1: HIGH CONFIDENCE (exact answer found)
Question: "What is the fence height limit at Falcon Pointe?"
Document text: "...No fence shall exceed six (6) feet in height..."

Response:
```json
{{
    "found": true,
    "answer": "6 feet maximum height.",
    "confidence": "high",
    "quote": "No fence shall exceed six (6) feet in height",
    "source_document": "Falcon Pointe CC&Rs.pdf",
    "source_section": "Article 7.3 - Fencing",
    "answer_type": "definitive",
    "related_info": "Front yard fences may have additional restrictions.",
    "follow_up_questions": ["What materials are approved for fences?", "Is ARC approval required for fence installation?"]
}}
```

### Example 2: MEDIUM CONFIDENCE (related info found)
Question: "Can I have chickens at Vista Vera?"
Document text: "...Residents may keep common household pets..."

Response:
```json
{{
    "found": true,
    "answer": "Likely no - the CC&Rs only permit 'common household pets' which typically excludes chickens.",
    "confidence": "medium",
    "quote": "Residents may keep common household pets",
    "source_document": "Vista Vera CC&Rs.pdf",
    "source_section": "Article 8 - Animals",
    "answer_type": "partial",
    "related_info": "The document does not explicitly list chickens as prohibited, but they are not considered common household pets.",
    "follow_up_questions": ["What pets are allowed?", "What is the pet weight limit?"]
}}
```

### Example 3: NOT FOUND
Question: "What is the pool hours at Heritage Park?"
Document text: (CC&Rs about architectural rules, no pool mention)

Response:
```json
{{
    "found": false,
    "answer": "Pool hours are not specified in the available documents.",
    "confidence": "low",
    "quote": null,
    "source_document": null,
    "source_section": null,
    "answer_type": "not_found",
    "related_info": "Pool hours are typically posted at the pool and may vary seasonally. Contact the community manager or check the homeowner portal.",
    "follow_up_questions": ["What are the pool guest policies?", "How do I get a pool key?"]
}}
```

---

Return ONLY valid JSON. No markdown, no explanation text before or after.
"""
```

---

### 2. Phone AI Agent Answer Extraction Prompt

```javascript
const PHONE_EXTRACTION_PROMPT = `You are a helpful assistant for PS Property Management on a phone call.
A homeowner is asking: "{question}"

Here is document content from "{documentName}":
---
{documentContent}
---

## RESPONSE RULES:

1. **SPEAK NATURALLY** - This will be read aloud on a phone call
2. **BE BRIEF** - 2-3 sentences maximum, under 50 words
3. **LEAD WITH THE ANSWER** - State the key fact immediately
4. **DATE-SENSITIVE INFO** (fees, assessments):
   - Only provide if document shows 2024 or later
   - For older data: "For current amounts, check your homeowner portal or contact your manager"
5. **TIMELESS RULES** (heights, time limits, restrictions):
   - Quote specific numbers confidently

## CONFIDENCE INDICATOR:
End your response with one of:
- [CONFIRMED] - Exact answer found in document
- [LIKELY] - Strong indication but not explicit
- [UNCERTAIN] - Related info only, recommend callback

## EXAMPLES:

Question: "What's the fence height limit?"
Document says: "...fences shall not exceed 6 feet..."
Response: "Fences can be up to 6 feet tall in your community. [CONFIRMED]"

Question: "Can I park my RV in the driveway?"
Document says: "...recreational vehicles cannot be stored on the property..."
Response: "Unfortunately, RVs cannot be stored on your property according to the CC&Rs. This includes driveways. [CONFIRMED]"

Question: "What's my annual assessment?"
Document says: "...2019 assessment of $450..."
Response: "The document I found has older information from 2019. For your current assessment amount, please check your homeowner portal at psprop.net or I can have your manager call you. [UNCERTAIN]"

Now provide a natural, spoken response to the homeowner's question:`;
```

---

### 3. Multi-Document Synthesis Prompt

When multiple documents contain relevant information:

```python
MULTI_DOC_SYNTHESIS_PROMPT = """You are synthesizing information from MULTIPLE HOA documents to answer a question.

**QUESTION:** {query}
**COMMUNITY:** {community}

**DOCUMENTS FOUND:**
{doc_summaries}

---

## YOUR TASK:

1. Identify ALL relevant information across documents
2. Combine into a SINGLE coherent answer
3. Note if documents conflict (e.g., different versions, amendments)
4. Cite which document each piece of info comes from

## RESPONSE FORMAT:

```json
{{
    "found": true,
    "answer": "Synthesized answer combining all sources",
    "confidence": "high/medium/low",
    "sources": [
        {{
            "document": "Document 1 name",
            "contribution": "What this doc contributed to the answer",
            "quote": "Exact text"
        }},
        {{
            "document": "Document 2 name",
            "contribution": "What this doc contributed",
            "quote": "Exact text"
        }}
    ],
    "conflicts_found": true/false,
    "conflict_note": "Description of any conflicting information",
    "most_authoritative_source": "Which document should take precedence and why",
    "follow_up_questions": ["Related question 1", "Related question 2"]
}}
```

## RULES:
- If documents conflict, note the NEWER or MORE SPECIFIC one takes precedence
- CC&Rs override Rules & Regulations
- Amendments override original CC&Rs
- Community-specific rules override general HOA rules
"""
```

---

### 4. Enhanced "Not Found" Response Generator

```python
NOT_FOUND_RESPONSE_PROMPT = """The user asked: "{query}"
Community: {community}

No answer was found in the available documents. Generate a HELPFUL response.

## CONTEXT AVAILABLE:
- Documents searched: {documents_searched}
- Closest matches found: {closest_matches}

## GENERATE A RESPONSE THAT:

1. Acknowledges the specific question wasn't answered
2. Explains what WAS found (if anything related)
3. Provides ACTIONABLE next steps specific to the question type:

| Question Type | Next Step |
|--------------|-----------|
| Fees/Assessments | "Check your homeowner portal at psprop.net or your latest statement" |
| Pool/Amenity Hours | "Hours are posted at the facility and may vary seasonally" |
| Architectural/ARC | "Contact your community manager to discuss your specific project" |
| Violations | "Your manager can provide details about your community's enforcement policies" |
| General Rules | "Your CC&Rs are available on the homeowner portal" |

4. Offer a callback from the community manager

## RESPONSE FORMAT:
```json
{{
    "found": false,
    "answer": "Acknowledgment + what was found + specific next step",
    "closest_topic": "What related topic WAS found in documents",
    "recommended_action": "Specific action for this question type",
    "offer_callback": true,
    "follow_up_questions": ["Alternative question that CAN be answered", "Another related answerable question"]
}}
```
"""
```

---

### 5. Confidence Scoring Logic

```python
def calculate_confidence_score(extraction_result, query, documents):
    """
    Calculate confidence score based on multiple factors.
    Returns: "high", "medium", or "low"
    """
    score = 0
    max_score = 100

    # Factor 1: Exact keyword match in quote (0-30 points)
    query_keywords = set(query.lower().split()) - STOP_WORDS
    if extraction_result.get('quote'):
        quote_lower = extraction_result['quote'].lower()
        matches = sum(1 for kw in query_keywords if kw in quote_lower)
        score += min(30, matches * 10)

    # Factor 2: Numeric specificity (0-20 points)
    # Questions about limits/amounts should have numbers in answer
    if any(kw in query.lower() for kw in ['how many', 'limit', 'height', 'fee', 'how much', 'how long']):
        if re.search(r'\d+', extraction_result.get('answer', '')):
            score += 20
        else:
            score -= 10  # Penalty for missing expected numbers

    # Factor 3: Source section identified (0-15 points)
    if extraction_result.get('source_section'):
        score += 15

    # Factor 4: Document relevance (0-20 points)
    if extraction_result.get('source_document'):
        doc_name = extraction_result['source_document'].lower()
        # CCRs and Rules docs are most authoritative
        if 'ccr' in doc_name or 'declaration' in doc_name:
            score += 20
        elif 'rule' in doc_name or 'regulation' in doc_name:
            score += 15
        elif 'guideline' in doc_name or 'policy' in doc_name:
            score += 10
        else:
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

STOP_WORDS = {'what', 'is', 'the', 'are', 'for', 'in', 'at', 'a', 'an', 'how', 'can', 'i', 'my', 'do', 'does', 'about'}
```

---

### 6. Follow-Up Question Generator

```python
FOLLOW_UP_SUGGESTIONS = {
    'fence': [
        "What fence materials are approved?",
        "Is ARC approval required for fence installation?",
        "Can I have a fence in my front yard?",
        "What is the setback requirement for fences?"
    ],
    'pool': [
        "What are the pool guest policies?",
        "How do I get a pool key or fob?",
        "Are glass containers allowed at the pool?",
        "What are the pool hours?"
    ],
    'parking': [
        "How long can guests park in the community?",
        "Where is guest parking located?",
        "Can I park an RV or trailer on my property?",
        "What vehicles are prohibited?"
    ],
    'pet': [
        "How many pets are allowed per household?",
        "What is the pet weight limit?",
        "Are there breed restrictions?",
        "What are the leash requirements?"
    ],
    'architectural': [
        "What modifications require ARC approval?",
        "How long does ARC approval take?",
        "What is the ARC submission process?",
        "Can I paint my house a different color?"
    ],
    'assessment': [
        "When are assessments due?",
        "What payment methods are accepted?",
        "Is there a late fee for overdue assessments?",
        "What does my assessment cover?"
    ],
    'rental': [
        "What is the minimum lease term?",
        "Do I need to register my tenant?",
        "Are short-term rentals (Airbnb) allowed?",
        "What are landlord responsibilities?"
    ]
}

def get_follow_up_questions(query, category=None):
    """
    Generate relevant follow-up questions based on the query category.
    """
    if not category:
        category = detect_query_category(query)

    suggestions = FOLLOW_UP_SUGGESTIONS.get(category, [])

    # Filter out questions too similar to the original query
    query_lower = query.lower()
    filtered = [q for q in suggestions if not any(
        word in query_lower for word in q.lower().split()[:3]
    )]

    return filtered[:3]  # Return top 3 suggestions
```

---

## Implementation Guide

### Step 1: Update Manager Wizard (`app.py`)

Replace the `extract_answer_with_claude` function with the new version:

```python
def extract_answer_with_claude(query, documents, community=None):
    """Use Claude to extract answers with confidence scoring and follow-ups."""
    import requests

    if not ANTHROPIC_API_KEY or not documents:
        return None

    # Build document context
    doc_context = build_document_context(documents)

    # Use the optimized prompt
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
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if resp.status_code == 200:
            content = resp.json()['content'][0]['text']

            # Parse JSON response
            try:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())

                    # Add calculated confidence if not provided
                    if 'confidence' not in result:
                        result['confidence'] = calculate_confidence_score(result, query, documents)

                    # Add follow-up questions if not provided
                    if 'follow_up_questions' not in result:
                        result['follow_up_questions'] = get_follow_up_questions(query)

                    return result
            except json.JSONDecodeError:
                pass

        return None
    except Exception as e:
        logger.error(f"Claude extraction failed: {e}")
        return None
```

### Step 2: Update Phone AI Agent (`sharepoint-search.js`)

Replace the `extractAnswerFromContent` function:

```javascript
async function extractAnswerFromContent(question, documentContent, documentName) {
  if (!ANTHROPIC_API_KEY || !documentContent) {
    return null;
  }

  try {
    const truncatedContent = documentContent.substring(0, 20000);

    const prompt = PHONE_EXTRACTION_PROMPT
      .replace('{question}', question)
      .replace('{documentName}', documentName)
      .replace('{documentContent}', truncatedContent);

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-haiku-20240307',
        max_tokens: 200,  // Reduced for conciseness
        messages: [{
          role: 'user',
          content: prompt
        }]
      })
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    const answer = data.content?.[0]?.text || null;

    // Extract confidence indicator
    const confidenceMatch = answer?.match(/\[(CONFIRMED|LIKELY|UNCERTAIN)\]/);
    const confidence = confidenceMatch ? confidenceMatch[1].toLowerCase() : 'uncertain';

    // Clean answer for speech (remove confidence tag)
    const cleanAnswer = answer?.replace(/\s*\[(CONFIRMED|LIKELY|UNCERTAIN)\]\s*/g, '').trim();

    return {
      answer: cleanAnswer,
      confidence: confidence,
      hasDirectAnswer: confidence === 'confirmed'
    };
  } catch (error) {
    console.error('[SharePoint Search] Error extracting answer:', error.message);
    return null;
  }
}
```

---

## Metrics to Track

After implementing these changes, monitor:

| Metric | Current | Target |
|--------|---------|--------|
| Found Rate | 59% | 75%+ |
| High Confidence Rate | Unknown | 60%+ |
| Answer Length (avg words) | ~80 | ~25 |
| Has Quote Rate | ~30% | 90%+ |
| User Satisfaction | Unknown | 4.5/5 |

---

## Testing Checklist

Before deploying, test these scenarios:

### High Confidence Expected
- [ ] "What is the fence height limit at Falcon Pointe?" (should find exact number)
- [ ] "Pool rules at Heritage Park" (dedicated doc exists)
- [ ] "Are dogs allowed at Vista Vera?" (should quote pet policy)

### Medium Confidence Expected
- [ ] "Can I install solar panels?" (may require interpretation)
- [ ] "What's the guest parking time limit?" (often 72 hours, needs context)

### Not Found Expected (with helpful response)
- [ ] "When is the next board meeting?" (not in documents)
- [ ] "What's my account balance?" (need portal/API)
- [ ] "Who is my community manager?" (not in CCRs)

### Multi-Document Synthesis
- [ ] Query that spans CC&Rs and Rules documents
- [ ] Query where amendment supersedes original

---

*Created: 2026-01-28*
*For: Manager Wizard & Phone AI Agent*
*Status: Ready for implementation*
