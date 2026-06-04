# AgriGuard QR/Product Browser Evidence

- Captured at: 2026-06-04T09:49:02.880Z
- Base URL: http://127.0.0.1:5174
- Product: Organic Apple (dbb58381-d19a-49dd-8b9f-c4ae47107c2a)
- QR session: qr-1780566541244-zaps2d0g
- Protected actions locked: true
- Screenshot: docs/reports/2026-06/agriguard-qr-product-clicks.png
- Console warnings/errors: 0
- Page errors: 0
- App/API request failures: 0
- External QR image failures: 0

## Captured QR Events
```json
[
  {
    "source": "qr_reader",
    "variant_id": "qr_page_v1",
    "occurred_at": "2026-06-04T09:49:01.400Z",
    "event_payload": {
      "attempt": 1
    },
    "session_id": "qr-1780566541244-zaps2d0g",
    "event_type": "scan_start"
  },
  {
    "source": "qr_reader",
    "variant_id": "qr_page_v1",
    "occurred_at": "2026-06-04T09:49:02.258Z",
    "event_payload": {
      "product_name": "Organic Apple",
      "origin": "Korea",
      "requires_cold_chain": false
    },
    "session_id": "qr-1780566541244-zaps2d0g",
    "event_type": "verification_complete",
    "product_id": "dbb58381-d19a-49dd-8b9f-c4ae47107c2a"
  }
]
```

## QR Event Responses
```json
[
  {
    "url": "http://127.0.0.1:8002/qr-events",
    "status": 200
  },
  {
    "url": "http://127.0.0.1:8002/qr-events",
    "status": 200
  }
]
```

## One Hour QR Summary
```json
{
  "hours": 1,
  "variant_id": "qr_page_v1",
  "since": "2026-06-04T08:49:02.854317+00:00Z",
  "total_events": 21,
  "total_sessions": 10,
  "event_counts": {
    "scan_start": 16,
    "scan_failure": 3,
    "verification_complete": 2
  },
  "error_counts": {
    "scanner_runtime_error": 3
  },
  "variant_counts": {
    "qr_page_v1": 21
  },
  "funnel": {
    "scan_start_sessions": 10,
    "scan_failure_sessions": 3,
    "scan_recovery_sessions": 0,
    "verification_complete_sessions": 2,
    "verification_completion_rate": 0.2,
    "recovery_rate_after_failure": 0
  }
}
```

## Console Warnings And Errors
```json
[]
```

## Page Errors
```json
[]
```

## App/API Request Failures
```json
[]
```

## External QR Image Failures
```json
[]
```
