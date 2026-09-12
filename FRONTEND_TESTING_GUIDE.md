# 🧪 Frontend Testing Guide - Complete Walkthrough

## 📋 Prerequisites Checklist

Before testing, verify:

```bash
# 1. Check if FAISS index exists
ls data/processed/faiss_index/

# 2. Check if .env has Groq API key
cat .env | grep GROQ_API_KEY

# 3. Check if dependencies are installed
pip list | grep -E "fastapi|groq|langchain|faiss"
```

**If missing:**
```bash
# Build FAISS index
python scripts/build_index.py

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Step 1: Start the Backend Server

```bash
# From project root directory
cd D:\Customer_support

# Activate virtual environment
.venv\Scripts\activate  # Windows
# OR: source .venv/bin/activate  # Mac/Linux

# Start FastAPI server
uvicorn customer_support.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Verify Server is Running:**
```bash
# In a new terminal
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

---

## 🌐 Step 2: Open the Frontend

### Option A: Customer Chat Interface

Open your browser and go to:
```
http://localhost:8000/
```

**What You Should See:**
- 🛡️ Sidebar with "Support AI" logo
- 5-step pipeline explanation
- Chat area with welcome message
- Input box at the bottom

### Option B: Human Review Dashboard (HITL)

```
http://localhost:8000/review
```

**What You Should See:**
- Queue statistics (Pending, Approved, Rejected counts)
- List of escalated cases
- Filter dropdown (All, Pending, Approved, Rejected)
- Auto-refresh indicator

---

## 🧪 Step 3: Test Cases

### **Test Case 1: Simple Delivery Query (Should AUTO_HANDLE)**

**Input:**
```
Where is my order? It says out for delivery but hasn't arrived yet.
```

**Expected Behavior:**
- ✅ Decision: **AUTO_HANDLE** (green badge)
- Intent: `delivery_status`
- Confidence: HIGH (>70%)
- Evidence Quality: STRONG or MODERATE
- Draft response appears immediately
- **Does NOT appear in review dashboard**

**What to Check:**
1. Response makes sense and is grounded
2. No forbidden phrases like "your refund has been processed"
3. Pipeline metadata shows all green flags
4. Grounding refs listed (e.g., EV-12345)

---

### **Test Case 2: Refund Request (Should ESCALATE - Financial Risk)**

**Input:**
```
I want a refund for my broken laptop. It stopped working after 2 days.
```

**Expected Behavior:**
- ⚠️ Decision: **ESCALATE** (orange badge)
- Intent: `refund_return` or `product_issue`
- Escalation Reason: "financial_risk_intent" or "sensitive intent requires human review"
- Draft response may still be shown
- **DOES appear in review dashboard**

**What to Check:**
1. Orange "Escalate" badge visible
2. Escalation reason box appears
3. Open **http://localhost:8000/review** in new tab
4. Verify case appears in "Pending" queue

---

### **Test Case 3: Explicit Human Request (Should ESCALATE)**

**Input:**
```
This is ridiculous! I want to speak to a real person right now.
```

**Expected Behavior:**
- ⚠️ Decision: **ESCALATE**
- Escalation Reason: "explicit_human_request"
- "Human Requested" field: **Yes**
- Intent: Likely `human_assistance_request` or `customer_service_complaint`

**What to Check:**
1. System catches human request phrases
2. Case escalates immediately regardless of confidence/evidence
3. Appears in review dashboard

---

### **Test Case 4: Ambiguous Message (Should ESCALATE - Low Confidence)**

**Input:**
```
Help me please something is wrong
```

**Expected Behavior:**
- ⚠️ Decision: **ESCALATE**
- Intent: `UNKNOWN` or low-confidence classification
- Escalation Reason: "intent_unknown" or "low_confidence"
- Confidence: LOW (<70%)

---

### **Test Case 5: Complaint (Should ESCALATE - Sensitive Intent)**

**Input:**
```
Your customer service is terrible! I've been waiting 2 weeks for my refund and nobody is helping me!
```

**Expected Behavior:**
- ⚠️ Decision: **ESCALATE**
- Intent: `customer_service_complaint`
- Escalation Reason: "sensitive intent (customer_service_complaint) requires human review"
- High Risk: 🔴 Yes

---

### **Test Case 6: Account Access Issue (Should ESCALATE)**

**Input:**
```
I can't log into my account. I've tried resetting my password but the email never arrives.
```

**Expected Behavior:**
- ⚠️ Decision: **ESCALATE**
- Intent: `account_access`
- Escalation Reason: "sensitive intent requires human review"

---

### **Test Case 7: Simple Product Question (Should AUTO_HANDLE)**

**Input:**
```
Does this come in blue color?
```

**Expected Behavior:**
- ✅ Decision: **AUTO_HANDLE**
- Intent: `availability_question` or `pricing_query`
- Confidence: HIGH
- Evidence: May be WEAK (depends on historical data)

---

## 🔍 Step 4: Test the Review Dashboard (HITL Workflow)

After sending **Test Cases 2, 3, 5, and 6**, open the review dashboard:

```
http://localhost:8000/review
```

### **4.1: View Pending Escalations**

**What to Check:**
1. All escalated cases appear in the queue
2. Each card shows:
   - Customer message
   - AI draft response
   - Escalation reason
   - Intent, confidence %, evidence quality
   - Timestamp
   - Three action buttons

### **4.2: Test "Approve & Send" Action**

1. Find an escalation with a good AI draft
2. Click **"✅ Approve & Send"**
3. **Expected:**
   - Card turns green
   - Status changes to "APPROVED"
   - Timestamp updates to "Resolved at: ..."
   - Moves to "Approved" filter

### **4.3: Test "Edit Response" Action**

1. Click **"✏️ Edit Response"** on any pending case
2. Modal/editor appears with AI draft
3. Edit the text (e.g., add: "We sincerely apologize for the inconvenience.")
4. Click **"💾 Save & Send"**
5. **Expected:**
   - Edited version saved
   - Status: APPROVED
   - Final response shows your edits

### **4.4: Test "Reject & Write Custom" Action**

1. Click **"❌ Reject & Write Custom"**
2. Write completely new response
3. Click **"📤 Send Custom Response"**
4. **Expected:**
   - AI draft ignored
   - Custom response saved
   - Status: REJECTED
   - Shows in "Rejected" filter

### **4.5: Test Filters**

1. Change filter dropdown:
   - **All** - Shows everything
   - **Pending** - Only unresolved
   - **Approved** - AI draft kept (maybe edited)
   - **Rejected** - AI draft replaced

2. **Expected:**
   - Queue updates immediately
   - Stats at top update

---

## 🎨 Step 5: Check UI/UX Features

### **Chat Interface Features:**

| Feature | What to Test |
|---------|-------------|
| **Typing Indicator** | Appears while processing (3 bouncing dots) |
| **Decision Badges** | Green for AUTO_HANDLE, Orange for ESCALATE |
| **Escalation Box** | Orange box with reason when escalated |
| **Pipeline Metadata** | Click "🔍 Pipeline Details" to expand/collapse |
| **Clear Button** | Top-right button clears conversation |
| **Error Handling** | Stop server, send message → shows connection error |

### **Review Dashboard Features:**

| Feature | What to Test |
|---------|-------------|
| **Auto-Refresh** | Stats update every 30 seconds |
| **Empty State** | Shows when no escalations exist |
| **Stats Counter** | Updates after approve/reject actions |
| **Timestamp** | Shows relative time (e.g., "2 minutes ago") |
| **Action Buttons** | All three actions work per case |

---

## 🐛 Step 6: Error Testing

### **6.1: Test Invalid Input**

**Input:** (empty message)
- Form should prevent submission (HTML5 validation)

### **6.2: Test Server Offline**

1. Stop the FastAPI server (Ctrl+C)
2. Send a message in chat
3. **Expected:**
   - ⚠️ Connection error message appears
   - Shows command to restart server

### **6.3: Test API Rate Limits**

Send 10+ messages rapidly:
- Some may fail with Groq API rate limit errors
- Errors appear in "Pipeline errors" section
- Decision defaults to ESCALATE

---

## 📊 Step 7: Verify Data Persistence

### **7.1: Check Escalation Storage**

```bash
# View stored escalations
cat escalations_queue.json | jq .

# Should show JSON with all escalations
```

### **7.2: Restart Server and Check Persistence**

1. Approve/reject some escalations
2. Stop server (Ctrl+C)
3. Restart server
4. Open review dashboard
5. **Expected:** All previous escalations still visible

---

## 🧪 Step 8: API Testing (Advanced)

### **8.1: Test Chat API Directly**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "current_message": "Where is my order?",
    "brand_id": "AmazonHelp",
    "context_turns": []
  }'
```

**Expected:** Full JSON response with all pipeline metadata

### **8.2: Test Escalation Queue API**

```bash
# Get pending escalations
curl http://localhost:8000/escalations?status=PENDING

# Get escalation stats
curl http://localhost:8000/escalations | jq '.stats'

# Approve an escalation
curl -X POST http://localhost:8000/escalations/{escalation_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "test_agent",
    "human_response": "Thank you for your patience..."
  }'
```

---

## 📈 Step 9: Performance Testing

### **9.1: Measure Latency**

Open browser DevTools (F12) → Network tab:
1. Send a message
2. Check `/chat` request
3. **Expected:** Response time 5-15 seconds (depends on Groq API)

### **9.2: Check Memory Usage**

```bash
# Monitor backend process
top -p $(pgrep -f uvicorn)

# Check if memory grows over time (memory leak detection)
```

---

## ✅ Success Criteria

Your frontend is working correctly if:

| Criteria | Status |
|----------|--------|
| ✅ Chat interface loads at `localhost:8000/` | |
| ✅ Review dashboard loads at `localhost:8000/review` | |
| ✅ Simple queries get AUTO_HANDLE decision | |
| ✅ Refund/complaint queries get ESCALATE decision | |
| ✅ Escalated cases appear in review dashboard | |
| ✅ Approve/Edit/Reject actions work | |
| ✅ Pipeline metadata displays correctly | |
| ✅ Error messages show when server offline | |
| ✅ Data persists after server restart | |
| ✅ Auto-refresh works in review dashboard | |

---

## 🎓 Pro Tips

### **Tip 1: Test with Real Amazon Support Scenarios**

```
- "My package was marked delivered but I never received it"
- "I was charged twice for the same order"
- "Cancel my Prime membership and give me a refund"
- "The item I received is damaged, what should I do?"
```

### **Tip 2: Test Edge Cases**

```
- Very long messages (500+ words)
- Messages in other languages (should escalate)
- Emoji-only messages (😡😡😡)
- Messages with URLs/emails
```

### **Tip 3: Monitor Backend Logs**

Watch the terminal where uvicorn is running:
```
INFO:     [pred-abc123] Processing message: Where is my order?...
INFO:     [pred-abc123] Decision: AUTO_HANDLE | Intent: delivery_status
INFO:     [pred-def456] ESCALATE → Added to escalation queue
```

### **Tip 4: Use Browser DevTools**

- **Console (F12):** Check for JavaScript errors
- **Network:** See API request/response details
- **Application → Storage:** Check if any data cached

---

## 🐛 Troubleshooting

### **Problem: "Connection Error" in Chat**

**Solution:**
```bash
# Verify server is running
curl http://localhost:8000/health

# Check if port 8000 is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # Mac/Linux

# Restart server
uvicorn customer_support.api.main:app --reload --port 8000
```

### **Problem: All Messages Escalate (Nothing Auto-Handles)**

**Possible Causes:**
1. FAISS index missing → Evidence always WEAK/NONE
2. Groq API key invalid → Classification fails
3. Router thresholds too strict

**Solution:**
```bash
# Rebuild FAISS index
python scripts/build_index.py

# Check API key
python -c "from customer_support.config.setting import get_settings; print(get_settings().GROQ_API_KEY)"

# Check router settings
grep -r "INTENT_CONFIDENCE_THRESHOLD" src/customer_support/config/
```

### **Problem: Review Dashboard Shows Empty**

**Possible Causes:**
1. No escalations yet (all messages auto-handled)
2. JavaScript error preventing load

**Solution:**
1. Send a complaint message to force escalation
2. Open browser console (F12) to check for errors
3. Verify API endpoint works:
   ```bash
   curl http://localhost:8000/escalations
   ```

### **Problem: Slow Response Times (>30 seconds)**

**Possible Causes:**
1. Groq API rate limiting
2. FAISS index too large
3. Slow embeddings model

**Solution:**
1. Add rate limit delays: `--delay 2` in evaluation
2. Use smaller embedding model in `retriever.py`
3. Check Groq API dashboard for quota limits

---

## 🎯 Next Steps After Testing

1. **Collect Metrics:**
   - Auto-handle rate (should be ~40-60%)
   - Escalation reasons distribution
   - Average latency

2. **Tune Router Rules:**
   - Adjust confidence thresholds in `router.py`
   - Add/remove intents from `ALWAYS_ESCALATE_INTENTS`

3. **Improve UI:**
   - Add conversation history tracking
   - Show evidence snippets in UI
   - Add user feedback buttons (👍👎)

4. **Production Readiness:**
   - Add authentication for review dashboard
   - Replace JSON storage with PostgreSQL
   - Add logging and monitoring
   - Deploy to cloud (AWS/GCP/Azure)

---

## 📚 Quick Reference

### **URLs:**
- Chat Interface: `http://localhost:8000/`
- Review Dashboard: `http://localhost:8000/review`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### **Files to Edit:**
- `frontend/script.js` - Chat UI logic
- `frontend/review.js` - Dashboard logic
- `src/customer_support/agent/router.py` - Escalation rules
- `src/customer_support/config/setting.py` - Thresholds

### **Key Commands:**
```bash
# Start server
uvicorn customer_support.api.main:app --reload --port 8000

# Run evaluation
python scripts/run_evaluation.py --limit 10

# Build index
python scripts/build_index.py

# Check logs
tail -f logs/app.log  # if logging configured
```

---

**Total Testing Time:** ~30-45 minutes  
**Coverage:** UI, API, HITL workflow, error handling, persistence  
**Result:** Confidence in production deployment 🚀
