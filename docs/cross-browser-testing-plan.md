# Manager Wizard - Cross-Browser Testing Plan
## Copy-as-Image Feature Compatibility

**Document Version:** 1.0
**Created:** 2026-01-28
**Purpose:** Ensure copy-as-image feature works reliably for staff pasting into Outlook/Gmail

---

## Executive Summary

The Manager Wizard's copy-as-image feature uses two key technologies:
1. **html2canvas v1.4.1** - Captures DOM elements as canvas/PNG
2. **Clipboard API** - `navigator.clipboard.write()` with `ClipboardItem`

Based on research, **Chrome and Edge are the recommended browsers** for staff. Firefox has limited support, and Safari/iOS have significant issues.

---

## Browser Compatibility Matrix

| Browser | html2canvas | Clipboard API | Paste to Outlook | Paste to Gmail | Recommended |
|---------|-------------|---------------|------------------|----------------|-------------|
| **Chrome 120+** | Full | Full | Yes | Yes | **Primary** |
| **Edge 120+** | Full | Full | Yes | Yes | **Primary** |
| **Firefox 126+** | Full | Limited | Ctrl+V only | Ctrl+V only | Fallback |
| **Safari 16.4+** | Partial | Limited | Limited | Limited | Not Recommended |
| **iOS Safari** | Problematic | Limited | No | No | Not Supported |
| **Android Chrome** | Full | Full | N/A | Yes | Supported |

### Legend
- **Full**: Works without issues
- **Limited**: Works with workarounds
- **Partial**: May have rendering issues
- **Problematic**: Frequent failures reported

---

## Detailed Browser Analysis

### 1. Google Chrome (Latest - v120+)

**Status: FULLY SUPPORTED**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Working | Best performance, optimized canvas operations |
| ClipboardItem API | Working | Native support since v66 |
| Paste to Outlook Web | Working | Requires clipboard permission enabled |
| Paste to Outlook Desktop | Working | Works via Ctrl+V |
| Paste to Gmail | Working | Full support |

**Known Issues:** None significant

**Test Procedure:**
1. Navigate to Manager Wizard
2. Search for a document (e.g., "fence rules Falcon Pointe")
3. Wait for AI answer to appear
4. Click "Copy for Email" button
5. Verify "Copied!" confirmation appears
6. Open Outlook (web or desktop)
7. Create new email, press Ctrl+V
8. Verify image appears with question text and answer card

**Expected Result:** Image pastes cleanly with:
- Query text at top (20px font with quotes)
- AI answer card with green gradient
- Source quote if present
- No copy button visible in image

---

### 2. Microsoft Edge (Latest - v120+)

**Status: FULLY SUPPORTED**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Working | Chromium-based, same as Chrome |
| ClipboardItem API | Working | Native support |
| Paste to Outlook Web | Working | Best integration (same vendor) |
| Paste to Outlook Desktop | Working | Optimal for PSPM staff |
| Paste to Gmail | Working | Full support |

**Known Issues:** None significant

**Test Procedure:** Same as Chrome

**Why Edge is Recommended for Staff:**
- Same rendering engine as Chrome (Chromium)
- Better Outlook integration
- Pre-installed on Windows machines
- Microsoft ecosystem consistency

---

### 3. Mozilla Firefox (v126+)

**Status: PARTIAL SUPPORT**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Working | Full support |
| ClipboardItem API | Limited | Only works via user interaction |
| Paste to Outlook Web | Limited | Must use Ctrl+V, right-click paste blocked |
| Paste to Outlook Desktop | Working | Ctrl+V works |
| Paste to Gmail | Working | Ctrl+V works |

**Known Issues:**
1. **Clipboard Permissions:** Firefox doesn't support `clipboard-write` permission
2. **Right-click paste blocked:** Outlook web doesn't show paste in context menu
3. **Async timing:** Safari-style promise requirement may cause issues

**Workarounds:**
- Use keyboard shortcut (Ctrl+V) instead of right-click
- Download fallback will trigger if clipboard fails

**Test Procedure:**
1. Same steps as Chrome
2. **CRITICAL:** When pasting, use Ctrl+V only
3. If right-click paste fails, this is expected behavior

**Expected Result:**
- Copy should work (or fallback to download)
- Paste works with Ctrl+V
- Right-click paste may fail

---

### 4. Safari (macOS - v16.4+)

**Status: NOT RECOMMENDED**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Partial | 10x slower than Chrome, font issues |
| ClipboardItem API | Limited | Only works in user gesture context |
| Paste to Outlook Web | Limited | Inconsistent behavior |
| Paste to Outlook Desktop | N/A | No Outlook desktop for Mac anymore |
| Paste to Gmail | Limited | Works with Ctrl+V |

**Known Issues:**
1. **Performance:** 30 seconds for complex DOM vs 3 seconds in Chrome
2. **Font Rendering:** FontAwesome icons may appear blank
3. **Word Spacing:** Letter/word spacing may render incorrectly
4. **Async Clipboard:** Must be triggered by direct user gesture
5. **Canvas Tainting:** May report cross-origin errors even for local content

**Workarounds:**
- Download fallback should catch most failures
- Recommend using Chrome on Mac instead

**Test Procedure:**
1. Same steps as Chrome
2. Expect possible "Downloaded" message instead of "Copied"
3. If downloaded, manually attach image to email

---

### 5. iOS Safari (iPhone/iPad)

**Status: NOT SUPPORTED**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Problematic | Frequent blank/white images |
| ClipboardItem API | Blocked | iOS doesn't support image clipboard |
| Paste to Outlook App | No | Cannot paste images from web |
| Paste to Gmail App | No | Cannot paste images from web |

**Known Issues:**
1. **Stuck at document clone:** Process hangs on "Starting document clone"
2. **Blank images:** Returns white/blank canvas
3. **No clipboard write:** iOS blocks image clipboard from web apps
4. **Memory limits:** Large canvas operations may crash

**Recommendation:**
- Staff should NOT use iOS for this feature
- Use desktop browser or Android device

---

### 6. Android Chrome

**Status: SUPPORTED**

| Feature | Status | Notes |
|---------|--------|-------|
| html2canvas rendering | Working | Same as desktop Chrome |
| ClipboardItem API | Working | Supported on Android Chrome |
| Paste to Outlook App | Limited | Depends on Outlook app version |
| Paste to Gmail App | Working | Full support |

**Test Procedure:**
1. Navigate to Manager Wizard on Android Chrome
2. Perform search, click "Copy for Email"
3. If "Copied!" appears, open Gmail app
4. Compose email, long-press to paste
5. Verify image appears

**Notes:** Mobile use case is rare for staff - desktop is primary

---

## Fallback Behavior Testing

The implementation includes a fallback when `ClipboardItem` fails:

```javascript
// Function: copyAnswerAsImage(btn)
// Located in: templates/index.html (lines 2599-2683)

} catch (clipErr) {
    console.error('Clipboard write failed:', clipErr);
    // Fallback: download the image
    const link = document.createElement('a');
    link.download = 'answer.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
    btn.innerHTML = '<i class="fas fa-download"></i> Downloaded';
}
```

### Fallback Test Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Clipboard blocked by browser | Download triggered, button shows "Downloaded" |
| Clipboard permission denied | Download triggered |
| Secure context required (HTTP) | Download triggered |
| ClipboardItem not available | Download triggered |

**Test Procedure:**
1. Open Chrome DevTools (F12)
2. Go to Application > Storage > Clear Site Data
3. Reload page
4. When clipboard permission prompt appears, click "Block"
5. Try copy-as-image
6. Verify file downloads as `answer.png`
7. Open downloaded file and verify content

---

## Outlook Integration Testing

### Outlook Web (outlook.office.com)

**Pre-requisites:**
1. Enable clipboard access in browser settings
   - Chrome: Settings > Privacy > Site Settings > Clipboard > Allow for outlook.office.com
   - Edge: Same process

**Test Matrix:**

| Browser | Copy | Paste Method | Result |
|---------|------|--------------|--------|
| Chrome | Working | Ctrl+V | Image inline |
| Chrome | Working | Right-click > Paste | Image inline |
| Edge | Working | Ctrl+V | Image inline |
| Edge | Working | Right-click > Paste | Image inline |
| Firefox | Working | Ctrl+V | Image inline |
| Firefox | Working | Right-click > Paste | FAILS (expected) |

### Outlook Desktop (Windows)

| Browser | Copy | Paste Method | Result |
|---------|------|--------------|--------|
| Chrome | Working | Ctrl+V | Image inline |
| Edge | Working | Ctrl+V | Image inline |
| Firefox | Working | Ctrl+V | Image inline |

**Note:** Right-click paste works in desktop Outlook regardless of browser used.

---

## Gmail Integration Testing

### Gmail Web (mail.google.com)

| Browser | Copy | Paste Method | Result |
|---------|------|--------------|--------|
| Chrome | Working | Ctrl+V | Image inline |
| Chrome | Working | Right-click > Paste | Image inline |
| Edge | Working | Ctrl+V | Image inline |
| Firefox | Working | Ctrl+V | Image inline |

**Note:** Gmail has excellent clipboard support across browsers.

---

## Microsoft Word Testing

Staff may also paste into Word documents.

| Browser | Copy | Paste (Ctrl+V) | Result |
|---------|------|----------------|--------|
| Chrome | Working | Working | Image inline |
| Edge | Working | Working | Image inline |
| Firefox | Working | Working | Image inline |
| Safari | Limited | Limited | May need Paste Special |

---

## Recommendations for Staff

### Primary Browsers (Use These)
1. **Microsoft Edge** - Best overall for Outlook integration
2. **Google Chrome** - Excellent alternative, same engine

### Acceptable Browsers
3. **Firefox** - Works, but must use Ctrl+V to paste

### Not Recommended
4. **Safari** - Performance and reliability issues
5. **iOS Safari** - Does not work for image clipboard
6. **Internet Explorer** - Not supported (deprecated)

### Quick Reference Card for Staff

```
HOW TO COPY AI ANSWERS FOR EMAIL:
================================
1. Search in Manager Wizard
2. Click "Copy for Email" button
3. Wait for "Copied!" confirmation
4. Open Outlook/Gmail
5. Press Ctrl+V (not right-click!)
6. Image appears in email

IF "DOWNLOADED" APPEARS:
- File saved as answer.png
- Attach manually to email

BROWSER TO USE: Edge or Chrome
AVOID: Safari, iPhone/iPad
```

---

## Known Limitations

### Current Implementation Limitations

1. **No browser detection:** Code doesn't detect browser or warn users
2. **No mobile optimization:** UI not optimized for mobile copying
3. **No retry mechanism:** Single attempt, then fallback

### Potential Improvements (Future)

1. Add browser detection and show warning for Safari/iOS
2. Add clipboard permission check before attempting copy
3. Consider html-to-image library as alternative for Safari
4. Add "How to paste" tooltip with browser-specific instructions

---

## Test Execution Checklist

### Pre-Testing Setup
- [ ] Clear browser cache and cookies
- [ ] Enable clipboard permissions for manager-wizard domain
- [ ] Prepare Outlook (web and desktop) for paste testing
- [ ] Prepare Gmail for paste testing

### Chrome Testing
- [ ] Copy-as-image works
- [ ] Paste to Outlook Web (Ctrl+V)
- [ ] Paste to Outlook Web (right-click)
- [ ] Paste to Outlook Desktop
- [ ] Paste to Gmail
- [ ] Fallback download works when clipboard blocked

### Edge Testing
- [ ] Copy-as-image works
- [ ] Paste to Outlook Web (Ctrl+V)
- [ ] Paste to Outlook Web (right-click)
- [ ] Paste to Outlook Desktop
- [ ] Paste to Gmail
- [ ] Fallback download works when clipboard blocked

### Firefox Testing
- [ ] Copy-as-image works
- [ ] Paste to Outlook Web (Ctrl+V only)
- [ ] Paste to Outlook Desktop
- [ ] Paste to Gmail
- [ ] Fallback download works

### Safari Testing (Optional - Not Recommended)
- [ ] Document any rendering issues
- [ ] Document clipboard failures
- [ ] Verify fallback download works

### Mobile Testing (Optional)
- [ ] Android Chrome - document behavior
- [ ] iOS Safari - confirm NOT working

---

## Issue Tracking

| Issue | Browser | Status | Workaround |
|-------|---------|--------|------------|
| Right-click paste fails | Firefox + Outlook Web | Known | Use Ctrl+V |
| Slow rendering (30s+) | Safari | Known | Use Chrome |
| Blank image | iOS Safari | Known | Use desktop |
| FontAwesome missing | Safari | Known | Acceptable (minor) |

---

## References

- [html2canvas Documentation](https://html2canvas.hertzen.com/documentation.html)
- [html2canvas GitHub Issues](https://github.com/niklasvh/html2canvas/issues)
- [MDN Clipboard API](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API)
- [MDN ClipboardItem](https://developer.mozilla.org/en-US/docs/Web/API/ClipboardItem)
- [web.dev Clipboard Patterns](https://web.dev/patterns/clipboard/paste-images)
- [Safari Clipboard Workarounds](https://wolfgangrittner.dev/how-to-use-clipboard-api-in-safari/)
- [Can I Use - Canvas](https://caniuse.com/canvas)

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| QA | | | |
| Product Owner | | | |

---

*Document generated by Claude Code - 2026-01-28*
