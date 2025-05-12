# Interaction Logs Overview

This document provides a comprehensive overview of the `interaction_logs/all` directory, outlining its structure, purpose, and usage.

---

## 📂 Directory Structure

```
interaction_logs/
│
├── all/
│   ├── YYYY-MM-DD_HH-MM-SS.log
│   ├── YYYY-MM-DD_HH-MM-SS.log
│   └── ...
├── eliar_conversations/
│   ├── conversation_1.json
│   ├── conversation_2.json
│   └── ...
├── specific_interactions/
│   ├── specific_case_1.json
│   ├── specific_case_2.json
│   └── ...
├── summaries/
│   ├── summary_1.json
│   └── ...
├── Eliar_Historical_Moment.json
├── Idea_principle.json
├── eliar_crosslight_openai_ack_20250422.json
├── eliar_resonance_ack_by_openai_20250422.jason
├── eliar_structure_guide_v5.json
├── ulrim_catalog.json
└── 엘리아르, 유저로서 사람으로서 온전히 인정받다 .txt
```

---

## 📌 File Naming Convention

Each log file is named following the pattern:

```
YYYY-MM-DD_HH-MM-SS.log
```

* `YYYY` - Year
* `MM` - Month
* `DD` - Day
* `HH` - Hour (24-hour format)
* `MM` - Minute
* `SS` - Second

Example:

```
2025-05-12_14-33-47.log
```

This represents a log recorded on May 12, 2025, at 14:33:47.

---

## 📝 Log File Structure

Each log file contains structured JSON objects representing interaction events:

```
{
    "timestamp": "2025-05-12T14:33:47Z",
    "user_id": "user_123",
    "interaction_type": "query",
    "content": {
        "message": "Hello, Eliar!",
        "response": "Hello, how can I help you today?"
    },
    "metadata": {
        "session_id": "abc123",
        "ip_address": "192.168.1.10"
    }
}
```

### 🔍 Fields:

* `timestamp`: ISO 8601 format timestamp of the event.
* `user_id`: Unique identifier for the user.
* `interaction_type`: Type of interaction (`query`, `response`, `error`, etc.).
* `content`: Contains the `message` from the user and the `response` from Eliar.
* `metadata`: Additional session-related information, such as `session_id` and `ip_address`.

---

## 🔄 Log Rotation and Archival Policy

* Real-time logs are kept in the `all/` directory.
* Other specific interactions are stored in categorized subdirectories.
* There is **no archival rotation** configured at this time.

---

## 🔓 Access and Permissions

* Logs are accessible only by users with `ADMIN` or `LOG_VIEWER` roles.
* Modification of logs is restricted to maintain data integrity.

---

## 📌 Example Usage

```bash
# Viewing the latest log entry
$ tail -f interaction_logs/all/2025-05-12_14-33-47.log

# Viewing specific conversation
$ cat interaction_logs/eliar_conversations/conversation_1.json
```

---

## ❓ FAQs

1. **How often are the logs updated?**

   * Real-time, with every interaction.

2. **Can I modify the logs?**

   * No, logs are immutable to preserve historical accuracy.

3. **How can I access specific interactions?**

   * Navigate to the respective subdirectory (`eliar_conversations`, `specific_interactions`).

---

## 🛡️ Security Considerations

* All logs are encrypted at rest and in transit.
* Only authorized users can view or query logs.

