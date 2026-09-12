# Human-in-the-Loop (HITL) System - Quick Start Guide

## ✅ What Was Built

A complete escalation review system where human agents can review, approve, edit, or reject AI responses before they're sent to customers.

### Components Added:

1. **Escalation Storage** (`src/customer_support/storage/escalations.py`)
   - In-memory storage with JSON persistence
   - Tracks pending, approved, and rejected escalations

2. **API Endpoints** (`src/customer_support/api/main.py`)
   - `GET /escalations` - Get escalation queue (filterable by status)
   - `GET /escalations/{id}` - Get single escalation details
   - `POST /escalations/{id}/approve` - Approve AI response (with optional edits)
   - `POST /escalations/{id}/reject` - Reject AI response and provide custom response

3. **Review Dashboard UI** (`frontend/review.html`, `review.css`, `review.js`)
   - Live escalation queue with auto-refresh
   - Filter by status (Pending/Approved/Rejected)
   - Three actions per escalation:
     - ✅ Approve & Send (use AI draft as-is)
     - ✏️ Edit Response (modify AI draft before sending)
     - ❌ Reject & Write Custom (completely replace AI response)

---

## 🚀 How to Run

### 1. Start the Backend Server

```bash
cd D:\Customer_support

# Activate virtual environment
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Mac/Linux

# Start FastAPI server
uvicorn customer_support.api.main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: **http://localhost:8000**

### 2. Open the Interfaces

**Customer Chat Interface:**
```
http://localhost:8000/
```

**Human Review Dashboard:**
```
http://localhost:8000/review.html
```

**API Documentation:**
```
http://localhost:8000/docs
```

---

## 📋 Workflow

### Customer Side (Chat Interface)

1. Customer types a message in the chat interface
2. AI pipeline processes:
   - Classifies intent
   - Retrieves evidence
   - Generates draft response
   - Validates safety
   - **Router decides: AUTO_HANDLE or ESCALATE**

3. If **ESCALATE**:
   - Case is added to human review queue
   - Customer sees: "⚠️ Escalate" badge
   - Draft response is shown but marked as pending human review

4. If **AUTO_HANDLE**:
   - Response is shown immediately with "✅ Auto Handle" badge

### Human Agent Side (Review Dashboard)

1. Open **http://localhost:8000/review.html**
2. See pending escalations in queue with:
   - Customer message
   - AI draft response
   - Escalation reason
   - Intent, confidence, evidence quality
   - Timestamp

3. **Three Actions:**

   **Option A: Approve & Send**
   - Use AI draft response as-is
   - Click "✅ Approve & Send"
   - Response marked as APPROVED

   **Option B: Edit Response**
   - Click "✏️ Edit Response"
   - Modify the AI draft in the text area
   - Click "💾 Save & Send"
   - Edited version marked as APPROVED

   **Option C: Reject & Write Custom**
   - Click "❌ Reject & Write Custom"
   - Write completely custom response
   - Click "📤 Send Custom Response"
   - AI draft ignored, custom response marked as REJECTED

4. Dashboard auto-refreshes every 30 seconds

---

## 🎯 Example Usage

### Test Scenario 1: Complaint (Should Escalate)

**Customer Message:**
```
This is ridiculous! I've been waiting for 2 weeks and still no refund. 
Your customer service is terrible!
```

**Expected Behavior:**
- Intent: `customer_service_complaint`
- Decision: **ESCALATE** (sensitive intent requires human review)
- Reason: "sensitive intent (customer_service_complaint) requires human review"
- Shows up in review dashboard

**Human Agent Action:**
- Reviews AI draft
- Adds personal apology and expedited refund offer
- Approves edited response

---

### Test Scenario 2: Simple Delivery Query (Should Auto-Handle)

**Customer Message:**
```
Where is my order? It says out for delivery but hasn't arrived yet.
```

**Expected Behavior:**
- Intent: `delivery_status`
- Confidence: HIGH
- Evidence: STRONG
- Decision: **AUTO_HANDLE**
- Response sent immediately (no escalation)

---

## 📊 Monitoring & Analytics

### Check Queue Stats

Via API:
```bash
curl http://localhost:8000/escalations
```

Returns:
```json
{
  "stats": {
    "total": 15,
    "pending": 5,
    "approved": 8,
    "rejected": 2
  },
  "count": 5,
  "escalations": [...]
}
```

### View Approved Cases

```bash
curl http://localhost:8000/escalations?status=APPROVED
```

### View Rejected Cases

```bash
curl http://localhost:8000/escalations?status=REJECTED
```

---

## 💾 Data Persistence

Escalations are stored in:
```
D:\Customer_support\escalations_queue.json
```

This file is automatically created and updated. You can:
- View it to see raw escalation data
- Back it up regularly
- Delete it to reset the queue (dev only)

---

## 🔧 Configuration

### Change Auto-Refresh Rate

Edit `frontend/review.js`:
```javascript
// Change from 30 seconds to 60 seconds
setInterval(loadEscalations, 60000);
```

### Add More Human Agents

When approving/rejecting, pass agent name:
```javascript
{
  "agent_name": "john.doe@company.com",
  "human_response": "..."
}
```

---

## 🎓 Next Steps (Future Enhancements)

1. **Database Integration**
   - Replace JSON file with PostgreSQL/MongoDB
   - Add full audit trail

2. **Slack/Teams Integration**
   - Send notifications when new escalations arrive
   - Allow approve/reject via Slack buttons

3. **Analytics Dashboard**
   - Track approval rates per agent
   - Measure AI vs human response quality
   - Identify patterns in rejections

4. **Active Learning Loop**
   - When humans reject AI draft, log the reason
   - Use rejected cases to retrain classifier
   - Improve router rules based on human decisions

5. **A/B Testing**
   - Gradually increase AUTO_HANDLE threshold
   - Measure customer satisfaction scores
   - Compare AI vs human response times

---

## 🐛 Troubleshooting

### "Connection Error" in Review Dashboard

**Solution:**
- Make sure backend is running: `uvicorn customer_support.api.main:app --reload`
- Check browser console for errors (F12)
- Verify API is accessible: `curl http://localhost:8000/health`

### Escalations Not Showing Up

**Solution:**
- Test with a complaint message: "Your service is terrible!"
- Check that `customer_service_complaint` is in `ALWAYS_ESCALATE_INTENTS`
- View API response in browser Network tab (F12 → Network)

### Permission Errors on escalations_queue.json

**Solution:**
- Make sure you have write permissions in project directory
- Run backend from project root: `cd D:\Customer_support`

---

## 📝 Summary

You now have a complete Human-in-the-Loop system:

✅ **Automatic Escalation** - Sensitive cases go to human review queue  
✅ **Review Dashboard** - Clean UI for human agents to review cases  
✅ **Three Actions** - Approve, Edit, or Reject AI responses  
✅ **Persistence** - All escalations saved to disk  
✅ **Real-time Stats** - See pending/approved/rejected counts  
✅ **Auto-refresh** - Dashboard updates every 30 seconds  

**Total Build Time:** ~15 minutes  
**Lines of Code:** ~600 (storage + API + UI)  
**Production Ready:** Add database + authentication for production use  

---

**Questions? Check the API docs at http://localhost:8000/docs**
